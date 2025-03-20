import time
import argparse
from typing import Dict, List, Tuple
from . import llm

# # 模型名称映射：根据基础模型名和平台名，提供平台特定的模型名称
# MODEL_MAPPINGS: Dict[str, Dict[str, str]] = {
#     "qwen-2.5-32b": {
#         "groq": "qwen-2.5-32b",
#         "deepseek": "deepseek-chat",
#         "aliyun": "qwen2.5-32b-instruct",
#         "siliconflow": "Qwen/Qwen2.5-32B-Instruct"
#     },
#     "qwen-qwq-32b": {
#         "groq": "qwen-qwq-32b",
#         "deepseek": "deepseek-chat",
#         "aliyun": "qwq-32b-preview",
#         "siliconflow": "Qwen/QwQ-32B"
#     }
# }

# def get_platform_model_name(base_model: str, platform: str) -> str:
#     """根据基础模型名和平台名，获取平台特定的模型名称"""
#     if base_model not in MODEL_MAPPINGS:
#         raise ValueError(f"未知的基础模型: {base_model}")

#     if platform not in MODEL_MAPPINGS[base_model]:
#         raise ValueError(f"平台 {platform} 不支持模型 {base_model}")

#     return MODEL_MAPPINGS[base_model][platform]

def benchmark_llm(base_model: str, platforms: List[str], prompt: str, max_tokens: int = 1024) -> List[Tuple[str, float, str]]:
    """
    对指定的模型在不同平台上进行基准测试

    Args:
        base_model: 基础模型名称
        platforms: 要测试的平台列表
        prompt: 测试提示词
        max_tokens: 最大生成token数

    Returns:
        包含(平台名, 耗时, 响应内容)的列表
    """
    results = []

    for platform in platforms:
        try:
            messages = [{"role": "user", "content": prompt}]

            print(f"测试 {platform} 平台的 {base_model} 模型...")

            start_time = time.time()
            response = llm.get_response_from_llm(
                messages=messages,
                model=base_model,
                max_tokens=max_tokens,
                platform=platform
            )
            end_time = time.time()

            elapsed_time = end_time - start_time
            results.append((platform, elapsed_time, response))

            print(f"平台: {platform}, 模型: {base_model}, 耗时: {elapsed_time:.2f}秒")

        except Exception as e:
            print(f"测试 {platform} 平台时出错: {str(e)}")
            results.append((platform, -1, f"错误: {str(e)}"))

    return results

def main():
    parser = argparse.ArgumentParser(description="LLM 基准测试工具")
    parser.add_argument("--model", type=str, default="qwen-2.5-32b", help="要测试的基础模型名称")
    parser.add_argument("--platforms", type=str, nargs="+",
                        default=["groq", "deepseek", "aliyun", "siliconflow"],
                        help="要测试的平台列表")
    parser.add_argument("--prompt", type=str, default="写一首14行诗歌颂自由",
                        help="测试提示词")
    parser.add_argument("--max-tokens", type=int, default=1024,
                        help="最大生成token数")

    args = parser.parse_args()

    print(f"开始测试模型 {args.model} 在以下平台的性能: {', '.join(args.platforms)}")
    print(f"提示词: '{args.prompt}'")
    print("-" * 50)

    results = benchmark_llm(
        base_model=args.model,
        platforms=args.platforms,
        prompt=args.prompt,
        max_tokens=args.max_tokens
    )

    print("\n" + "=" * 50)
    print("测试结果汇总:")
    print("=" * 50)

    # 按耗时排序
    valid_results = [(p, t, r) for p, t, r in results if t > 0]
    valid_results.sort(key=lambda x: x[1])

    for platform, elapsed_time, response in valid_results:
        print(f"平台: {platform}")
        print(f"耗时: {elapsed_time:.2f}秒")
        print(f"响应摘要: {response[:100]}..." if len(response) > 100 else response)
        print("-" * 50)

    # 显示错误结果
    error_results = [(p, t, r) for p, t, r in results if t < 0]
    if error_results:
        print("\n出错的平台:")
        for platform, _, error in error_results:
            print(f"{platform}: {error}")

if __name__ == "__main__":
    main()