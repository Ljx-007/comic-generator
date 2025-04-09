import os
import json
import base64
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
import yaml
# 加载环境变量
# load_dotenv()

with open('config.yml','r') as f:
    config=yaml.safe_load(f)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'development-key')

# API相关配置
IMAGE_API_URL = "https://api.siliconflow.cn/v1/images/generations"
TEXT_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_TOKEN = config['APIKey']

# 问题列表
QUESTIONS = [
    "请描述故事的主角和背景",
    "请描述故事的开始情节",
    "请描述故事的中间发展",
    "请描述故事的结局"
]

@app.route('/')
def index():
    # 重置会话
    session.clear()
    return render_template('index.html')

@app.route('/questions', methods=['GET', 'POST'])
def questions():
    if request.method == 'POST':
        # 获取当前问题索引
        current_question = session.get('current_question', 0)
        
        # 保存回答
        if current_question < len(QUESTIONS):
            answer = request.form.get('answer', '')
            answers = session.get('answers', [])
            
            if current_question < len(answers):
                answers[current_question] = answer
            else:
                answers.append(answer)
                
            session['answers'] = answers
            
            # 更新问题索引
            current_question += 1
            session['current_question'] = current_question
            
            # 如果所有问题都回答完毕，生成图像
            if current_question >= len(QUESTIONS):
                return redirect(url_for('generate_prompts'))
        
        return redirect(url_for('questions'))
    
    # GET请求，显示当前问题
    current_question = session.get('current_question', 0)
    if current_question >= len(QUESTIONS):
        return redirect(url_for('generate_prompts'))
    
    question = QUESTIONS[current_question]
    answers = session.get('answers', [])
    current_answer = answers[current_question] if current_question < len(answers) else ""
    
    return render_template('questions.html', 
                          question=question, 
                          question_number=current_question + 1, 
                          total_questions=len(QUESTIONS),
                          current_answer=current_answer)

@app.route('/generate_prompts')
def generate_prompts():
    # 获取所有回答
    answers = session.get('answers', [])
    
    if len(answers) < len(QUESTIONS):
        return redirect(url_for('questions'))
    
    # 使用文本模型生成更优化的提示词
    try:
        optimized_prompts = generate_optimized_prompts(answers)
        session['optimized_prompts'] = optimized_prompts
        return redirect(url_for('generate_images'))
    except Exception as e:
        print(f"Error generating prompts: {str(e)}")
        # 如果提示词生成失败，直接使用原始回答
        session['optimized_prompts'] = answers + ["故事结局和总结"] # 添加第五个提示词
        return redirect(url_for('generate_images'))

def generate_optimized_prompts(answers):
    """使用文本模型生成优化的提示词"""
    if not API_TOKEN:
        # 开发模式，返回测试提示词
        return answers + ["故事的结局和总结"]
    
    # 准备提示信息
    story_input = "\n".join([f"{i+1}. {QUESTIONS[i]}: {answers[i]}" for i in range(len(answers))])
    
    prompt = f"""
作为AI绘画提示词优化专家，请基于以下故事描述，生成5个连续的高质量提示词，用于生成连贯的漫画/绘本风格图像。
每个提示词应该详细描述一个场景，包含人物、环境、动作和情感等细节。
提示词应该具有连贯性，能够讲述一个完整的故事。

故事描述:
{story_input}

请直接输出5个优化后的提示词，使用JSON格式，不要有任何解释或额外文本。格式如下:
["提示词1", "提示词2", "提示词3", "提示词4", "提示词5"]

提示词要求:
1. 每个提示词约50-100字，详细且具体
2. 提示词必须用中文表达
3. 保持故事的连贯性和逻辑发展
4. 第5个提示词应该是故事的结局
"""
    
    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "max_tokens": 1024,
        "temperature": 0.7,
        "top_p": 0.7
    }
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(TEXT_API_URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # 尝试从内容中提取JSON
        try:
            # 查找JSON数组的起始和结束位置
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                prompts = json.loads(json_str)
                
                # 确保有5个提示词
                if len(prompts) >= 5:
                    return prompts[:5]
                else:
                    # 如果提示词少于5个，补充到5个
                    while len(prompts) < 5:
                        prompts.append(f"故事的继续发展 {len(prompts) + 1}")
                    return prompts
        except json.JSONDecodeError:
            print("Failed to parse JSON from model response")
    
    # 如果API调用失败或解析失败，使用原始回答并添加第五个提示词
    return answers + ["故事结局和总结"]  

@app.route('/generate_images')
def generate_images():
    # 获取优化后的提示词
    optimized_prompts = session.get('optimized_prompts', [])
    
    if len(optimized_prompts) < 5:
        return redirect(url_for('generate_prompts'))
    
    # 生成图像
    image_urls = []
    previous_image = None
    
    for i, prompt in enumerate(optimized_prompts):
        try:
            image_url = generate_image(prompt, previous_image)
            image_urls.append(image_url)
            
            # 更新previous_image用于下一次请求
            if image_url:
                # 这里如果需要，可以将image_url中的图片下载并转换为base64
                # 简化起见，我们在这个示例中不实现这个功能
                previous_image = None
                
        except Exception as e:
            print(f"Error generating image {i+1}: {str(e)}")
            image_urls.append(None)
    
    session['image_urls'] = image_urls
    session['prompts'] = optimized_prompts
    return redirect(url_for('result'))

def generate_image(prompt, previous_image=None):
    """调用API生成图像"""
    if not API_TOKEN:
        # 开发模式，返回测试URL
        return "https://via.placeholder.com/512x512.png?text=Generated+Image"
    
    payload = {
        "model": "Kwai-Kolors/Kolors",
        "prompt": prompt,
        "negative_prompt": "",
        "image_size": "1024x1024",
        "batch_size": 1,
        "seed": 4999999999,
        "num_inference_steps": 20,
        "guidance_scale": 7.5
    }
    
    # 如果有前一张图像，添加到请求中
    if previous_image:
        payload["image"] = previous_image
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(IMAGE_API_URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if 'images' in data and len(data['images']) > 0:
            return data['images'][0]['url']
    
    return None

@app.route('/result')
def result():
    image_urls = session.get('image_urls', [])
    answers = session.get('answers', [])
    prompts = session.get('prompts', [])
    
    if not image_urls or len(image_urls) < 5:
        return redirect(url_for('generate_images'))
    
    # 创建辅助数据以正确显示问题和提示词
    display_data = []
    for i in range(5):
        item = {
            'image_url': image_urls[i] if i < len(image_urls) else None,
            'prompt': prompts[i] if i < len(prompts) else "",
        }
        
        # 为前4项添加原始问题和答案
        if i < 4:
            item['question'] = QUESTIONS[i]
            item['answer'] = answers[i] if i < len(answers) else ""
        else:
            # 第5项没有对应的原始问题和答案
            item['question'] = "故事结局"
            item['answer'] = "基于前面的情节自动生成"
        
        display_data.append(item)
    
    return render_template('result.html', display_data=display_data)

if __name__ == '__main__':
    app.run(debug=config.get('Debug', True)) 