import streamlit as st
from dashscope import Application
from http import HTTPStatus
import os
import re
import sys
import json
import pandas as pd
from typing import Dict, Callable, List, Any

# 页面设置
st.set_page_config(page_title="Dior Product Assistant", page_icon="👗")
st.title("👗 Dior Product Bot")
st.caption("Powered by Qwen Max through Alibaba Cloud Bailian Platform")

# ===== 配置区 =====
with st.sidebar:
    st.image(f'images/截屏2025-05-09 17.19.08.png', width=150)
    st.header("About This Assistant", divider="gray")
    st.caption("Dior Couture | Product")
    st.write("""
    **Welcome to Dior Product Assistant**
    \nThis intelligent assistant is designed to help you learn about Dior Couture collections.
    """)

    st.header("Configuration")
    app_id = st.text_input("Bailian App ID", help="Your Bailian application ID")
    api_key = st.text_input("API Key", type="password", help="Bailian API secret key")

    with st.expander("Advanced Parameters"):
        temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
        top_p = st.slider("Top P", 0.0, 1.0, 0.9, 0.1)
        max_tokens = st.number_input("Max Tokens", min_value=1, max_value=4096, value=1024)

    st.divider()

# ===== 聊天区 =====
if not api_key or not app_id:
    st.warning("⚠️ Please provide App ID and API Key", icon="🔑")
    st.stop()

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": """
    Bonjour! Welcome to the Dior Product Assistant.
    \nHow can I help you today?
    """}]

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Bonjour! Welcome to the Dior Product Assistant.\nHow can I help you today?"}
    ]

if "doc_references" not in st.session_state:
    st.session_state.doc_references = {}  # 字典类型
if "show_stock_query" not in st.session_state:
    st.session_state.show_stock_query = False  # 布尔类型
if "stock_query" not in st.session_state:
    st.session_state.stock_query = {}  # 字典类型

# 辅助函数 - 显示图片
def show_image(doc_name):
    image_path = f'images/{doc_name}.png'
    if os.path.exists(image_path):
        st.image(image_path, caption=f"{doc_name}", use_container_width=True)
    else:
        st.warning(f"Image not found: {image_path}")
        st.image(f'images/截屏2025-05-09 17.19.08.png',
                 caption="Placeholder Image", use_container_width=True)

# 辅助函数 - 显示文档引用
def show_references(doc_references):
    st.divider()
    st.subheader("📚 References")

    for i, reference in enumerate(doc_references):
        if isinstance(reference, dict):
            for k, v in reference.items():
                st.caption(f"Reference {k}: {v}")
        else:
            st.caption(f"Reference {i + 1}: {reference}")

    with st.expander("🖼️ View Related Images"):
        for reference in doc_references:
            if isinstance(reference, dict):
                for k, doc_name in reference.items():
                    show_image(doc_name)
            else:
                show_image(reference)

# 辅助函数 - 显示库存查询
def show_stock_query():
    st.divider()
    st.subheader("📦 Stock Inquiry")

    # 创建三列布局
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.stock_query["mmc"] = st.text_input(
            "MMC",
            value=st.session_state.stock_query.get("mmc", ""),
            key="stock_mmc"
        )
    with col2:
        st.session_state.stock_query["size"] = st.text_input(
            "Size",
            value=st.session_state.stock_query.get("size", ""),
            key="stock_size"
        )
    with col3:
        st.session_state.stock_query["product"] = st.text_input(
            "Product Name",
            value=st.session_state.stock_query.get("product", ""),
            key="stock_product"
        )

    # 执行查询
    if st.button("🔍 Check Stock Availability") or st.session_state.auto_query:
        with st.spinner("Querying..."):
            result_df = query_stock(
                st.session_state.stock_query["mmc"],
                st.session_state.stock_query["size"],
                st.session_state.stock_query["product"]
            )

            if not result_df.empty:
                st.success(f"Found {len(result_df)} matching records")
                st.dataframe(result_df)
            else:
                st.warning("No matching inventory records found.")


# 新增：库存查询函数
@st.cache_data(ttl=600)  
def query_stock(mmc: str = None, size_code: str = None, product_name: str = None) -> pd.DataFrame:
    try:
        # 读取Excel文件
        file_path = "/workspaces/dior-product/Stock_Merged_Result.xlsx"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Stock File Not Found: {file_path}")

        df = pd.read_excel(file_path)

        # 根据条件过滤数据
        if mmc:
            filtered_df = df[df['mmc'] == mmc]
            if size_code:
                filtered_df = filtered_df[filtered_df['size_code'] == size_code]
        elif product_name:
            filtered_df = df[df['style_label'].str.contains(product_name, na=False, case=False)]
            if size_code:
                filtered_df = filtered_df[filtered_df['size_code'] == size_code]
        else:
            return pd.DataFrame()

        return filtered_df

    except Exception as e:
        st.error(f"Error in Stock Query: {str(e)}")
        return pd.DataFrame()


# 聊天机器人类 - 封装API调用逻辑
class ChatBot:
    def __init__(self, api_key: str, app_id: str):
        self.api_key = api_key
        self.app_id = app_id
        self.messages = []

    def ask(self, message: str, stream_callback: Callable[[str], None] = None) -> Dict:
        # 管理消息历史 - 保持对话长度适中
        if len(self.messages) >= 7:
            self.messages.pop(1)
            self.messages.pop(1)

        # 添加新用户消息
        self.messages.append({"role": "user", "content": message})

        # 调用API
        responses = Application.call(
            api_key=self.api_key,
            app_id=self.app_id,
            messages=self.messages,
            prompt=message,
            stream=True,
            incremental_output=True
        )

        # 处理流式响应
        rsp = ''
        doc_references = []
        stock_info = None
        for response in responses:
            if response.status_code != HTTPStatus.OK:
                print(f'request_id={response.request_id}')
                print(f'code={response.status_code}')
                print(f'message={response.message}')
                print(f'请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code')
            elif response.output.text is not None:
                try:
                    # 尝试解析JSON响应
                    response_data = json.loads(response.output.text)
                    chunk = response_data.get("result", "")
                    refs = response_data.get("doc_references", [])

                    # 新增：检查是否包含库存信息
                    if "stock" in response_data:
                        try:
                            # 先处理可能多余的包裹格式
                            stock_json = response_data["stock"]
                            if stock_json.startswith("```json\n") and stock_json.endswith("\n```"):
                                stock_json = stock_json[8:-3]
                            stock_data = json.loads(stock_json)
                            stock_info = stock_data
                        except json.JSONDecodeError:
                            stock_info = None

                    if stream_callback and chunk:
                        stream_callback(chunk)
                    print(chunk, end="", flush=True)
                    sys.stdout.flush()
                    rsp += chunk

                    # 收集文档引用
                    if refs:
                        doc_references = refs
                except json.JSONDecodeError:
                    # 如果不是JSON格式，直接使用原始文本
                    chunk = response.output.text
                    if stream_callback:
                        stream_callback(chunk)
                    print(chunk, end="", flush=True)
                    sys.stdout.flush()
                    rsp += chunk

        # 保存消息到历史
        self.messages.append({"role": "assistant", "content": rsp, "doc_references": doc_references, "stock_info": stock_info})

        return {"full_rsp": rsp, "doc_references": doc_references, "stock_info": stock_info}


# 初始化聊天机器人
if "chatbot" not in st.session_state:
    st.session_state.chatbot = ChatBot(api_key, app_id)


# 显示历史消息
for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

        # 如果是助手消息且有文档引用，显示引用和图片
        if msg["role"] == "assistant" and "doc_references" in msg and msg["doc_references"]:
            st.divider()
            st.subheader("📚 References")

            # 显示引用列表
            for i, reference in enumerate(msg["doc_references"]):
                if isinstance(reference, dict):
                    for k, v in reference.items():
                        st.caption(f"Reference {k}: {v}")
                else:
                    st.caption(f"Reference {i + 1}: {reference}")

            # 创建图片扩展区
            with st.expander("🖼️ View Related Images"):
                for reference in msg["doc_references"]:
                    if isinstance(reference, dict):
                        for k, doc_name in reference.items():
                            image_path = f'images/{doc_name}.png'

                            # 检查图片是否存在
                            if os.path.exists(image_path):
                                st.image(image_path, caption=f"{doc_name}", use_container_width=True)
                            else:
                                st.warning(f"Image not found: {image_path}")
                                st.image(f'images/截屏2025-05-09 17.19.08.png', caption="Placeholder Image", use_container_width=True)
                    else:
                        # 处理非字典类型的引用
                        image_path = f'images/{reference}.png'
                        if os.path.exists(image_path):
                            st.image(image_path, caption=f"{reference}", use_container_width=True)

            # 新增：如果有库存信息，直接调用查询函数并展示结果
            if "stock_info" in msg and msg["stock_info"]:
                st.divider()
                st.subheader("📦 Stock Query History")

                # 提取库存信息
                mmc = msg["stock_info"].get("mmc", "")
                size_code = msg["stock_info"].get("size_code", "")
                product_name = msg["stock_info"].get("product_name", "")

                # 执行查询
                with st.spinner("Querying stock availability..."):
                    result_df = query_stock(mmc, size_code, product_name)

                    # 显示结果
                    if not result_df.empty:
                        st.success(f"Found {len(result_df)} matching records")
                        st.dataframe(result_df)
                    else:
                        st.warning("No matching inventory records found. Please provide more information.")

# 显示当前库存查询部分（如果应该显示）
if st.session_state.show_stock_query:
    show_stock_query()

# 用户输入处理
if prompt := st.chat_input("Ask a question about Dior products..."):
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # 生成AI回复
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        resp_container = [""]

        def stream_callback(chunk: str) -> None:
            resp_container[0] += chunk
            message_placeholder.markdown(resp_container[0] + "▌")

        try:
            # 调用API
            response = st.session_state.chatbot.ask(prompt, stream_callback)

            # 处理响应
            full_response = response["full_rsp"]
            doc_references = response["doc_references"]
            stock_info = response["stock_info"]

            # 保存文档引用
            if doc_references:
                st.session_state.doc_references[len(st.session_state.messages)] = doc_references

            # 后处理回复
            cleaned_response = re.sub(r'<ref>.*?</ref>', '', full_response)
            hr_compliant_response = f"{cleaned_response}\n\n---\n*For more product information, please visit our official website.*"

            # 更新UI - 先显示清理后的回复
            message_placeholder.markdown(hr_compliant_response)

            # 立即显示文档引用（如果有）
            if doc_references:
                st.divider()
                st.subheader("📚 References")

                # 显示引用列表
                for i, reference in enumerate(doc_references):
                    if isinstance(reference, dict):
                        for k, v in reference.items():
                            st.caption(f"Reference {k}: {v}")
                    else:
                        st.caption(f"Reference {i + 1}: {reference}")

                # 创建图片扩展区
                with st.expander("🖼️ View Related Images"):
                    for reference in doc_references:
                        if isinstance(reference, dict):
                            for k, doc_name in reference.items():
                                image_path = f'images/{doc_name}.png'

                                # 检查图片是否存在
                                if os.path.exists(image_path):
                                    st.image(image_path, caption=f"{doc_name}", use_container_width=True)
                                else:
                                    st.warning(f"Image not found: {image_path}")
                                    st.image(f'images/截屏2025-05-09 17.19.08.png', caption="Placeholder Image", use_container_width=True)
                        else:
                            # 处理非字典类型的引用
                            image_path = f'images/{reference}.png'
                            if os.path.exists(image_path):
                                st.image(image_path, caption=f"{reference}", use_container_width=True)

            # 新增：如果有库存信息，直接调用查询函数并展示结果
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

            # 添加到会话历史
            st.session_state.messages.append({
                "role": "assistant",
                "content": hr_compliant_response,
                "doc_references": doc_references,
                "stock_info": stock_info
            })

        except Exception as e:
            error_msg = f"⚠️ Service unavailable. Technical details: {str(e)}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Apologies, we're experiencing technical difficulties. Please try again later or contact our technical service for assistance."
            })


# ===== 功能区 =====
# 侧边栏功能
with st.sidebar:
    if st.button("🔄 Clear Conversation"):
        st.session_state.messages = [{"role": "assistant", "content": "How can I help you today?"}]
        st.session_state.doc_references = {}
        st.session_state.show_stock_query = False
        st.session_state.chatbot = ChatBot(api_key, app_id)
        st.session_state.auto_query = False
        st.rerun()

    if st.button("❌ Hide Stock Query" if st.session_state.show_stock_query else "📦 Show Stock Query"):
        st.session_state.show_stock_query = not st.session_state.show_stock_query
        st.session_state.auto_query = False
        st.rerun()

    st.divider()
    st.caption("© 2025 Dior Product Assistant")
