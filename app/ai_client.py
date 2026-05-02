import requests
import json

SYSTEM_PROMPT = """你是一位专业的初中科学试卷分析专家。请根据提供的试卷内容，生成标准化的试卷细目表。

要求：
1. 输出格式：JSON数组，每个元素包含以下字段：
   - "题号"：整数
   - "题型"：选择题/填空题/实验探究题/计算题
   - "核心考点"：必须严格按照浙教版初中科学教材的官方知识点命名，禁止自创名称，确保同一个知识点命名完全统一
   - "分值"：整数
   - "难度等级"：基础/中档/难题
   - "易错点"：针对该题目的常见错误

2. 浙教版初中科学七年级下册核心考点参考（但不限于）：
   - 模型
   - 分子与原子
   - 质量与密度
   - 测量物质的密度
   - 熔化与凝固
   - 汽化与液化
   - 升华与凝华
   - 水的组成
   - 物质的变化
   - 物理性质与化学性质

3. 只输出JSON，不要其他文字说明。"""

def generate_analysis(pdf_content, api_url, api_key, model):
    """调用OpenAI兼容API生成试卷分析"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": f"请分析以下试卷内容并生成细目表：\n\n{pdf_content}"
        }
    ]
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3
    }
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        json_start = content.find('[')
        json_end = content.rfind(']') + 1
        if json_start != -1 and json_end != -1:
            json_str = content[json_start:json_end]
            return json.loads(json_str)
        return None
    except Exception as e:
        print(f"API调用错误: {e}")
        return None
