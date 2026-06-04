import os

print("=" * 60)
print("环境变量检查")
print("=" * 60)

env_vars = {
    "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
    "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
    "AZURE_OPENAI_API_INSTANCE_NAME": os.getenv("AZURE_OPENAI_API_INSTANCE_NAME"),
    "AZURE_OPENAI_API_DEPLOYMENT_NAME": os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME"),
    "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
}

for var_name, value in env_vars.items():
    if value:
        # 只显示前后各8个字符，中间用*表示
        if len(value) > 16:
            masked = f"{value[:8]}...{value[-8:]}"
        else:
            masked = value
        print(f"✅ {var_name}: {masked}")
    else:
        print(f"❌ {var_name}: 未找到")

print("=" * 60)
