import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Optional
import os
import json
import time
import re
from datetime import datetime

# 配置页面
st.set_page_config(
    page_title="Dior Product Bot",
    page_icon="💄",
    layout="wide"
)

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chatbot" not in st.session_state:
    st.session_state.chatbot = None

# 设置标题
st.title("Dior Product Bot")
st.markdown("Ask me anything about Dior products!")

# API 密钥输入
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Enter your API Key", type="password")
    app_id = st.text_input("Enter your App ID", type="password")
    
    if st.button("Initialize Chatbot"):
        if api_key and app_id:
            # 这里应该是初始化聊天机器人的代码
            # 由于不知道具体的实现，我们假设这是一个占位符
            class DiorChatbot:
                def __init__(self, api_key, app_id):
                    self.api_key = api_key
                    self.app_id = app_id
                    
                def ask(self, prompt, stream_callback=None):
                    # 模拟流式响应
                    full_response = ""
                    chunks = [
                        "Thank you for your inquiry about Dior products.",
                        "Dior offers a wide range of luxury products including skincare, makeup, fragrance, and fashion.",
                        "If you have a specific product in mind, please let me know and I can provide more information."
                    ]
                    
                    doc_references = [
                        {"title": "Dior Official Website", "url": "https://www.dior.com"},
                        {"title": "Dior Beauty Collection", "url": "https://www.dior.com/en_us/beauty"}
                    ]
                    
                    # 模拟从提示中提取库存信息
                    stock_info = None
                    if "stock" in prompt.lower() or "availability" in prompt.lower():
                        # 尝试从提示中提取MMC和尺码信息
                        mmc_match = re.search(r"MMC\s*[:=]?\s*(\d+)", prompt)
                        size_match = re.search(r"size\s*[:=]?\s*([A-Za-z0-9]+)", prompt)
                        product_name_match = re.search(r"product\s*[:=]?\s*([\w\s]+)", prompt)
                        
                        mmc = mmc_match.group(1) if mmc_match else ""
                        size_code = size_match.group(1) if size_match else ""
                        product_name = product_name_match.group(1) if product_name_match else ""
                        
                        if mmc or size_code:
                            stock_info = {
                                "mmc": mmc,
                                "size_code": size_code,
                                "product_name": product_name
                            }
                    
                    for chunk in chunks:
                        full_response += chunk + " "
                        if stream_callback:
                            stream_callback(chunk + " ")
                            time.sleep(0.2)  # 模拟网络延迟
                    
                    return {
                        "full_rsp": full_response,
                        "doc_references": doc_references,
                        "stock_info": stock_info
                    }
            
            st.session_state.chatbot = DiorChatbot(api_key, app_id)
            st.success("Chatbot initialized successfully!")
        else:
            st.error("Please provide both API Key and App ID")

def show_references(doc_references: List[Dict[str, str]]):
    st.divider()
    st.subheader("📚 References")
    for ref in doc_references:
        st.markdown(f"- [{ref['title']}]({ref['url']})")

def query_stock(mmc: str, size_code: str, product_name: str) -> pd.DataFrame:
    """查询产品库存信息"""
    # 模拟查询库存数据
    # 在实际应用中，这里应该连接到库存数据库或API
    time.sleep(1.5)  # 模拟查询延迟
    
    # 创建示例数据
    data = {
        "Store": ["Dior Boutique Paris", "Dior Boutique New York", "Dior Boutique Tokyo"],
        "Product": [product_name or "Dior Lipstick", product_name or "Dior Lipstick", product_name or "Dior Lipstick"],
        "MMC": [mmc or "87012345", mmc or "87012345", mmc or "87012345"],
        "Size": [size_code or "333", size_code or "999", size_code or "333"],
        "Availability": ["In Stock", "Out of Stock", "Limited Stock"],
        "Quantity": [15, 0, 3]
    }
    
    return pd.DataFrame(data)

# 显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "doc_references" in message:
            show_references(message["doc_references"])
        if message["role"] == "assistant" and "stock_info" in message and message["stock_info"]:
            stock_info = message["stock_info"]
            st.divider()
            st.subheader("📦 Stock Query")
            with st.spinner("Querying stock availability..."):
                result_df = query_stock(
                    stock_info.get("mmc", ""),
                    stock_info.get("size_code", ""),
                    stock_info.get("product_name", "")
                )
            if not result_df.empty:
                st.success(f"Found {len(result_df)} matching records")
                st.dataframe(result_df)
            else:
                st.warning("No matching inventory records found. Please provide more information.")

# 聊天输入
if "chatbot" in st.session_state and st.session_state.chatbot:
    if prompt := st.chat_input("Ask a question about Dior products..."):
        if api_key and app_id:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
            with st.chat_message("assistant", avatar="🤖"):
                message_placeholder = st.empty()
                resp_container = [""]
                def stream_callback(chunk: str) -> None:
                    resp_container[0] += chunk
                    message_placeholder.markdown(resp_container[0] + "▌")
                try:
                    response = st.session_state.chatbot.ask(prompt, stream_callback)
                    full_response = response["full_rsp"]
                    doc_references = response["doc_references"]
                    stock_info = response["stock_info"]
                    
                    # 添加合规性尾部提示
                    hr_compliant_response = f"{full_response}\n\n---\n*For more product information, please visit our official website.*"
                    message_placeholder.markdown(hr_compliant_response)
                    
                    if doc_references:
                        show_references(doc_references)

                    if stock_info:
                        st.divider()
                        st.subheader("📦 Stock Query")
                        # 提取库存信息
                        mmc = stock_info.get("mmc", "")
                        size_code = stock_info.get("size_code", "")
                        product_name = stock_info.get("product_name", "")
                        # 执行查询
                        with st.spinner("Querying stock availability..."):
                            result_df = query_stock(mmc, size_code, product_name)
                        # 显示结果
                        if not result_df.empty:
                            st.success(f"Found {len(result_df)} matching records")
                            st.dataframe(result_df)
                        else:
                            st.warning("No matching inventory records found. Please provide more information.")

                    # 更新会话状态
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": hr_compliant_response,
                        "doc_references": doc_references,
                        "stock_info": stock_info
                    })
                except Exception as e:
                    message_placeholder.error(f"⚠️ Error: {str(e)}")
        else:
            st.error("Please initialize the chatbot with valid API credentials")
else:
    st.info("Please initialize the chatbot in the sidebar")    
