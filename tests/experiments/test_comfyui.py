"""Tests for ComfyUI local image generation integration."""

from unittest.mock import MagicMock, patch
import pytest

from agentbook.comfyui import (
    build_default_qwen_workflow,
    generate_image_comfyui,
    is_comfyui_running,
    load_custom_workflow_template,
)


def test_build_default_qwen_workflow():
    wf = build_default_qwen_workflow("a red apple", negative_prompt="blurry")
    assert "3" in wf
    assert wf["3"]["class_type"] == "KSampler"
    assert wf["4"]["inputs"]["ckpt_name"] == "qwen_image_2.1.safetensors"
    assert wf["6"]["inputs"]["text"] == "a red apple"
    assert wf["7"]["inputs"]["text"] == "blurry"


def test_load_custom_workflow_template(tmp_path):
    template = {
        "1": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Positive Prompt"},
            "inputs": {"text": "placeholder"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Negative Prompt"},
            "inputs": {"text": "placeholder"},
        },
    }
    tf = tmp_path / "wf.json"
    tf.write_text('{"prompt": ' + __import__("json").dumps(template) + "}")

    loaded = load_custom_workflow_template(tf, "fresh cat", "lowres")
    assert loaded["1"]["inputs"]["text"] == "fresh cat"
    assert loaded["2"]["inputs"]["text"] == "lowres"


def test_is_comfyui_running():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert is_comfyui_running("http://127.0.0.1:8188") is True

    with patch("requests.get", side_effect=Exception("Connection refused")):
        assert is_comfyui_running("http://127.0.0.1:8188") is False


def test_generate_image_comfyui_mock_flow():
    mock_post_prompt = MagicMock()
    mock_post_prompt.status_code = 200
    mock_post_prompt.json.return_value = {"prompt_id": "test-prompt-123"}

    mock_history = MagicMock()
    mock_history.status_code = 200
    mock_history.json.return_value = {
        "test-prompt-123": {
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "out_001.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        }
    }

    mock_view = MagicMock()
    mock_view.status_code = 200
    mock_view.content = b"fake-png-bytes"
    mock_view.headers = {"Content-Type": "image/png"}

    def fake_get(url, *args, **kwargs):
        if "history" in url:
            return mock_history
        if "view" in url:
            return mock_view
        return MagicMock(status_code=404)

    def fake_post(url, *args, **kwargs):
        if "v1/images/generations" in url:
            return MagicMock(status_code=404)
        if "prompt" in url:
            return mock_post_prompt
        return MagicMock(status_code=404)

    with patch("requests.get", side_effect=fake_get), patch("requests.post", side_effect=fake_post):
        img_bytes, mime, record = generate_image_comfyui(
            "test prompt",
            base_url="http://127.0.0.1:8188",
            model="qwen_image_2.1",
        )
        assert img_bytes == b"fake-png-bytes"
        assert mime == "image/png"
        assert record["provider"] == "comfyui"
        assert record["model"] == "qwen_image_2.1"
        assert record["status"] == "ok"
