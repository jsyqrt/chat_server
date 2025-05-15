import openai
import os
import re
from typing import Dict, List, Tuple, Generator, Optional, Any
import time
from ..monitoring.api_monitor import APIMonitor, monitor_api_call  # 导入API监控工具
from flask import current_app

# 模型名称映射：根据基础模型名和平台名，提供平台特定的模型名称
MODEL_MAPPINGS: Dict[str, Dict[str, str]] = {
    "qwen-2.5-32b": {
        "groq": "qwen-2.5-32b",
        "deepseek": "deepseek-chat",
        "aliyun": "qwen2.5-32b-instruct",
        "siliconflow": "Qwen/Qwen2.5-32B-Instruct"
    },
    "qwen-qwq-32b": {
        "groq": "qwen-qwq-32b",
        "deepseek": "deepseek-chat",
        "aliyun": "qwq-32b-preview",
        "siliconflow": "Qwen/QwQ-32B"
    },
    "deepseek-r1" : {
        "groq": "qwen-qwq-32b",
        "deepseek": "deepseek-chat",
        "aliyun": "qwq-32b-preview",
        "siliconflow": "deepseek-ai/DeepSeek-R1"
    },
    "qwen-2.5-32b-vl": {
        "groq": "qwen-2.5-32b",
        "deepseek": "deepseek-chat",
        "aliyun": "qwen2.5-32b-instruct",
        "siliconflow": "Qwen/Qwen2.5-VL-32B-Instruct"
    }
}

def get_platform_model_name(base_model: str, platform: str) -> str:
    """根据基础模型名和平台名，获取平台特定的模型名称"""
    if base_model not in MODEL_MAPPINGS:
        raise ValueError(f"未知的基础模型: {base_model}")

    if platform not in MODEL_MAPPINGS[base_model]:
        raise ValueError(f"平台 {platform} 不支持模型 {base_model}")

    return MODEL_MAPPINGS[base_model][platform]

def get_api_url_and_key(platform="groq") -> Tuple[str, str]:
    """获取API URL和密钥，检查密钥是否存在"""
    api_url = ""
    api_key = ""

    if platform == "groq":
        api_url = "https://api.groq.com/openai/v1"
        api_key = os.environ.get("GROQ_API_KEY")
    elif platform == "deepseek":
        api_url = "https://api.deepseek.com/v1"
        api_key = os.environ.get("DEEPSEEK_API_KEY")
    elif platform == "aliyun":
        api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        api_key = os.environ.get("ALIYUN_API_KEY")
    elif platform == "siliconflow":
        api_url = "https://api.siliconflow.cn/v1"
        api_key = os.environ.get("SF_ZCHAT_API_KEY")
    else:
        current_app.logger.error(f"不支持的平台: {platform}")
        raise ValueError(f"不支持的平台: {platform}")

    if not api_key:
        current_app.logger.error(f"未找到平台 {platform} 的API密钥")
        raise ValueError(f"未找到平台 {platform} 的API密钥")

    return api_url, api_key

@monitor_api_call("llm_completion")  # 添加API监控装饰器
def get_response_from_llm(messages: List[Dict[str, str]], model: str, max_tokens: int, platform: str = "groq", retry_count: int = 3) -> str:
    """
    向LLM发送请求并获取完整响应

    Args:
        messages: 消息列表
        model: 模型名称
        max_tokens: 最大token数
        platform: 平台名称
        retry_count: 重试次数

    Returns:
        LLM的完整响应文本
    """
    last_error = None
    for attempt in range(retry_count):
        try:
            api_url, api_key = get_api_url_and_key(platform)
            platform_model = get_platform_model_name(model, platform)

            client = openai.OpenAI(
                base_url=api_url,
                api_key=api_key,
            )

            response = client.chat.completions.create(
                model=platform_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0,
            )

            return response.choices[0].message.content

        except Exception as e:
            last_error = e
            current_app.logger.error(f"LLM请求失败 (尝试 {attempt+1}/{retry_count}): {str(e)}")
            if attempt < retry_count - 1:
                # 指数退避重试
                time.sleep(2 ** attempt)
                continue
            else:
                # 最后一次尝试失败
                current_app.logger.error(f"所有LLM请求尝试均失败: {str(e)}")
                # 记录API调用失败 - 装饰器会自动处理，这里不需要额外记录
                raise RuntimeError(f"LLM请求失败: {str(e)}") from e

    # 这里应该不会到达，但为了安全起见
    if last_error:
        raise RuntimeError(f"LLM请求失败: {str(last_error)}") from last_error
    return "无法获取LLM响应，请稍后重试"

@monitor_api_call("llm_stream")  # 添加API监控装饰器
def get_response_from_llm_stream(messages: List[Dict[str, str]], model: str, max_tokens: int, platform: str = "groq") -> Generator[str, None, None]:
    """
    向LLM发送请求并流式获取响应

    Args:
        messages: 消息列表
        model: 模型名称
        max_tokens: 最大token数
        platform: 平台名称

    Yields:
        LLM响应的流式内容块
    """
    api_name = f"llm_stream_{platform}"
    try:
        api_url, api_key = get_api_url_and_key(platform)
        platform_model = get_platform_model_name(model, platform)

        client = openai.OpenAI(
            base_url=api_url,
            api_key=api_key,
        )

        response = client.chat.completions.create(
            model=platform_model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )

        # 记录成功的API调用
        APIMonitor.record_success(api_name)

        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        current_app.logger.error(f"LLM流式请求失败: {str(e)}")
        # 记录API调用失败
        APIMonitor.record_error(api_name)
        # 在流中发送错误标记
        yield f"\n\n[系统提示: 获取AI响应时出现错误，请重试或联系客服]"
        # 重新抛出异常以便上层处理
        raise RuntimeError(f"LLM流式请求失败: {str(e)}") from e

@monitor_api_call("llm_chat")  # 添加API监控装饰器
def chat_with_llm_stream(message: str, history: List[Dict[str, str]], model: str, max_tokens: int, platform: str = "groq") -> Generator[str, None, None]:
    """
    与LLM聊天，并流式获取响应

    Args:
        message: 用户消息
        history: 聊天历史
        model: 模型名称
        max_tokens: 最大token数
        platform: 平台名称

    Yields:
        LLM响应的流式内容块
    """
    messages = history.copy()  # 创建副本，避免修改原始历史记录
    messages.append({"role": "user", "content": message})

    try:
        yield from get_response_from_llm_stream(messages, model, max_tokens, platform)
    except Exception as e:
        current_app.logger.error(f"聊天流式请求失败: {str(e)}")
        # 异常已在get_response_from_llm_stream中处理，这里不需要再次发送错误消息

def get_json_blocks_from_llm_response(response: str) -> List[str]:
    """从LLM响应中提取JSON代码块"""
    try:
        # 定义正则表达式模式：匹配 ```json 和 ``` 之间的内容
        pattern = r'```json\n(.*?)\n```'

        # 查找所有匹配的代码块
        json_blocks = re.findall(pattern, response, re.DOTALL)

        return json_blocks
    except Exception as e:
        current_app.logger.error(f"提取JSON代码块失败: {str(e)}")
        return []

def get_html_blocks_from_llm_response(response: str) -> List[str]:
    """从LLM响应中提取HTML代码块"""
    try:
        # 定义正则表达式模式：匹配 ```html 和 ``` 之间的内容
        pattern = r'```html\n(.*?)\n```'

        # 查找所有匹配的代码块
        html_blocks = re.findall(pattern, response, re.DOTALL)

        return html_blocks
    except Exception as e:
        current_app.logger.error(f"提取HTML代码块失败: {str(e)}")
        return []
