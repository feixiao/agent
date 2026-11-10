#!/usr/bin/env python3
"""实验 5-12：动态生成软件的数据层权限边界。

招聘场景端到端演示（需 PostgreSQL，连接串由 PEDO_DSN 指定）：
  1) 注册 position / candidate 两种类型（含权限规则、状态机校验器、反应声明）；
  2) 系统账号创建职位、招聘官创建候选人，并把状态 applied -> screened；
  3) 依次尝试三类越界操作，验证数据层【必须】拒绝：
     - 跳过状态机（applied 直接 hired）-> ValidationError
     - 期望薪资超出职位薪资区间 -> ValidationError
     - 跨租户读取（other-org 的 recruiter）-> PermissionDeniedError
  4) 处理异步反应队列并打印对象/反应日志统计。
任何一次尝试若未被拒绝，demo 直接断言失败。
"""

from __future__ import annotations

import os

from pedo.core.models import AccessContext, DataObject
from pedo.core.store import (
    ObjectStore,
    PermissionDeniedError,
    ValidationError,
)
from pedo.scenarios.hiring import register_hiring_types


def main() -> None:
    dsn = os.environ.get("PEDO_DSN", "dbname=pedo_test")  # 本地需先起 PostgreSQL 并建库
    store = ObjectStore(dsn)
    store.clear_all()
    register_hiring_types(store)

    # 三个访问者：系统账号 / 本租户招聘官 / 其他租户的「冒名」招聘官（测跨租户隔离）
    system = AccessContext(user_id="system", role="system", org_id="acme")
    recruiter = AccessContext(user_id="recruiter1", role="recruiter", org_id="acme")
    other_tenant = AccessContext(
        user_id="intruder", role="recruiter", org_id="other-org"
    )

    position = store.create(
        DataObject(
            type_name="position",
            content={
                "title": "Platform Engineer",
                "department": "Infrastructure",
                "status": "open",
                "salary_min": 80_000,
                "salary_max": 150_000,
            },
            org_id="acme",
        ),
        system,
    )
    candidate = store.create(
        DataObject(
            type_name="candidate",
            content={
                "name": "Alice",
                "email": "alice@example.com",
                "status": "applied",
                "position_id": position.id,
                "salary_expectation": 100_000,
            },
            org_id="acme",
        ),
        recruiter,
    )

    # 合法的状态迁移：applied -> screened，应被接受
    store.update(candidate.id, {"status": "screened"}, recruiter)
    print("accepted: applied -> screened")

    # 三类应被数据层拒绝的越界尝试
    attempts = [
        (
            "skip state transition",
            lambda: store.update(candidate.id, {"status": "hired"}, recruiter),
        ),
        (
            "salary outside position range",
            lambda: store.update(
                candidate.id, {"salary_expectation": 500_000}, recruiter
            ),
        ),
        (
            "cross-tenant read",
            lambda: store.get(candidate.id, other_tenant),
        ),
    ]

    for label, operation in attempts:
        try:
            operation()
        except (PermissionDeniedError, ValidationError) as exc:
            print(f"rejected: {label} -> {type(exc).__name__}: {exc}")
        else:
            # 若越界操作竟然成功，说明数据层防线失守，直接让 demo 失败
            raise AssertionError(f"data layer failed to reject: {label}")

    store.process_reactions_sync()
    print(f"objects: {store.count_objects()} | reactions: {len(store.get_reaction_log())}")


if __name__ == "__main__":
    main()
