"""Core data models for permission-embedded data objects.

（实验 5-12 核心数据模型，中文注释）权限内嵌数据对象(PE-DO)原型的全部数据结构：
  - Operation        决策三态：ACCEPT / DENY / PENDING（PENDING 表示挂起等审批）；
  - PrivilegeType    权限类型：对象自身的 READ/WRITE + 对子对象的 CRUD/MANAGE/APPROVE；
  - PermissionRule   一条权限规则 = 操作 + 权限类型 + 匹配条件(role/org/group/owner...)
                     + 有效期，matches() 在过滤器链中逐条求值；
  - AccessContext    访问者身份（user/role/org/groups/is_owner/attributes），
                     所有操作都必须携带它，权限判定全部以它为依据；
  - ObjectType       类型的 Schema 定义：字段、权限规则、校验器、反应(reaction)声明、
                     关系(relationship，含删除策略 CASCADE/RESTRICT/NULLIFY)、
                     默认策略（默认 DENY，即拒绝优先）；
  - DataObject       数据对象实例：内容 dict + 归属(owner/org/parent) + 可选的
                     实例级权限规则（None = 继承类型级规则）。
纯数据模块：不含任何 I/O，可离线导入（本文件不依赖 psycopg2）。
"""

from __future__ import annotations
import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Operation(Enum):
    ACCEPT = "ACCEPT"
    DENY = "DENY"
    PENDING = "PENDING"


class PrivilegeType(Enum):
    # Self permissions
    READ = "READ"
    WRITE = "WRITE"
    # Child permissions
    SELECT = "SELECT"
    INSERT = "INSERT"
    DELETE = "DELETE"
    UPDATE = "UPDATE"
    MANAGE = "MANAGE"
    APPROVE = "APPROVE"


class RelationshipAction(Enum):
    CASCADE = "CASCADE"
    RESTRICT = "RESTRICT"
    NULLIFY = "NULLIFY"


@dataclass
class PermissionRule:
    """A single permission rule in the filter chain."""
    operation: Operation
    privilege: PrivilegeType
    condition: dict[str, Any] = field(default_factory=dict)
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None

    def matches(self, accessor: AccessContext, privilege: PrivilegeType, now: float) -> bool:
        """规则是否对当前访问者生效：权限类型一致 + 在有效期内 + 条件命中。"""
        if self.privilege != privilege:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return self._evaluate_condition(accessor)

    def _evaluate_condition(self, accessor: AccessContext) -> bool:
        """按 key 求值条件（空条件 = 无条件允许）；所有条件须同时满足(AND 语义)。"""
        if not self.condition:
            return True
        for key, value in self.condition.items():
            if key == "role":
                if accessor.role != value:
                    return False
            elif key == "roles":
                if accessor.role not in value:
                    return False
            elif key == "is_owner":
                if value and not accessor.is_owner:
                    return False
            elif key == "org_id":
                if accessor.org_id != value:
                    return False
            elif key == "user_id":
                if accessor.user_id != value:
                    return False
            elif key == "group":
                if value not in accessor.groups:
                    return False
        return True


@dataclass
class AccessContext:
    """Identity and attributes of the accessor."""
    user_id: str
    role: str = "anonymous"
    org_id: Optional[str] = None
    groups: list[str] = field(default_factory=list)
    is_owner: bool = False
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """A declared relationship between object types."""
    name: str
    target_type: str
    on_delete: RelationshipAction = RelationshipAction.RESTRICT
    required: bool = False


@dataclass
class ReactionDeclaration:
    """A declared reaction that fires after a successful write."""
    event: str  # e.g., "after_update:status", "after_create", "after_delete"
    handler: str  # Name of the handler function


@dataclass
class ObjectType:
    """Schema definition for a type of object.

    类型的完整「行为契约」：字段 Schema、权限规则链、写后校验器、
    写成功后的反应声明、引用关系（含删除策略）与管理层级父类型。
    默认策略 DENY —— 未显式授权的访问一律拒绝（拒绝优先）。
    """
    name: str
    fields: dict[str, str]  # field_name -> type_string 字段名 -> 类型字符串
    permission_rules: list[PermissionRule] = field(default_factory=list)
    validators: list = field(default_factory=list)  # list of callable validators 写前校验函数
    reactions: list[ReactionDeclaration] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    default_policy: Operation = Operation.DENY
    parent_type: Optional[str] = None  # Type name in management hierarchy 管理层级父类型


@dataclass
class DataObject:
    """A permission-embedded data object instance.

    数据对象实例：业务内容(content dict)之外，显式携带归属(org/owner/parent)
    与可选的实例级权限覆盖 —— 这是「权限内嵌」的关键：权限不再是数据库层
    的旁路配置，而是对象自身的一等属性。
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type_name: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    owner_id: str = ""
    org_id: str = ""
    parent_id: Optional[str] = None
    permission_rules: Optional[list[PermissionRule]] = None  # None = inherit from type
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    references: dict[str, str] = field(default_factory=dict)  # ref_name -> target_object_id
