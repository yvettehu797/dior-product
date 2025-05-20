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

# ===== 聊天区初始化 =====
if not api_key or not app_id:
    st.warning("⚠️ Please provide App ID and API Key", icon="🔑")
    st.stop()

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Bonjour! Welcome to the Dior Product Assistant.\nHow can I help you today?"}
    ]
if "doc_references" not in st.session_state:
    st.session_state.doc_references = []
if "show_stock_query" not in st.session_state:
    st.session_state.show_stock_query = False
if "stock_query" not in st.session_state:
    st.session_state.stock_query = {}

# 辅助函数 - 显示图片
def show_image(doc_name):
    image_path = f'images/{doc_name}.png'
    if os.path.exists(image_path):
        st.image(image_path, caption=f"{doc_name}", use_container_width=True)
    else:
        st.warning(f"Image not found: {image_path}")
        st.image(f'images/截屏2025-05-09 17.19.08.png', caption="Placeholder Image", use_container_width=True)

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
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.stock_query["mmc"] = st.text_input("MMC", key="stock_mmc")
    with col2:
        st.session_state.stock_query["size"] = st.text_input("Size", key="stock_size")
    with col3:
        st.session_state.stock_query["product"] = st.text_input("Product Name", key="stock_product")
    if st.button("🔍 Check Stock Availability", key="stock_check_btn"):
        with st.spinner("Querying..."):
            result_df = query_stock(**st.session_state.stock_query)
            if not result_df.empty:
                st.success(f"Found {len(result_df)} matching records")
                st.dataframe(result_df)
            else:
                st.warning("No matching inventory records found.")

# 库存查询函数
@st.cache_data(ttl=600)
def query_stock(mmc: str = None, size_code: str = None, product_name: str = None) -> pd.DataFrame:
    try:
        file_path = "Stock_Merged_Result.xlsx"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Stock File Not Found: {file_path}")
        df = pd.read_excel(file_path)
        filters = []
        if mmc:
            filters.append(df['mmc'] == mmc)
        if size_code:
            filters.append(df['size_code'] == size_code)
        if product_name:
            filters.append(df['style_label'].str.contains(product_name, na=False, case=False))
        if filters:
            filtered_df = df[pd.concat(filters, axis=1).all(axis=1)]
        else:
            filtered_df = pd.DataFrame()
        return filtered_df
    except Exception as e:
        st.error(f"Error in Stock Query: {str(e)}")
        return pd.DataFrame()

# 聊天机器人类（核心流式处理逻辑）
class ChatBot:
    def __init__(self, api_key: str, app_id: str):
        self.api_key = api_key
        self.app_id = app_id
        self.messages = []
        self.json_pattern = re.compile(r'({.*?})$', re.DOTALL)  # 匹配末尾JSON

    def ask(self, message: str, stream_callback: Callable[[str], None] = None) -> Dict:
        # 管理消息历史
        if len(self.messages) >= 7:
            self.messages.pop(1)
        self.messages.append({"role": "user", "content": message})
        
        full_rsp = ""
        doc_references = []
        in_json = False  # 标记是否进入JSON解析模式
        json_buffer = ""  # 不完整JSON缓冲区

        responses = Application.call(
            api_key=self.api_key,
            app_id=self.app_id,
            messages=self.messages,
            prompt=message,
            stream=True,
            incremental_output=True
        )

        for response in responses:
            if response.status_code != HTTPStatus.OK:
                print(f"API Error: {response.message}")
                continue
            
            chunk = response.output.text or ""
            
            # 检测JSON起始位置
            match = self.json_pattern.search(chunk)
            if match and not in_json:
                # 拆分自然语言和JSON部分
                natural_part = chunk[:match.start()].strip()
                json_part = chunk[match.start():]
                
                # 处理自然语言部分
                if natural_part:
                    self._stream_output(natural_part, stream_callback, full_rsp)
                
                # 开始处理JSON
                in_json = True
                json_buffer += json_part
            elif in_json:
                # 拼接不完整的JSON
                json_buffer += chunk
                try:
                    # 尝试解析完整JSON
                    json_data = json.loads(json_buffer)
                    self._process_json(json_data, stream_callback, full_rsp, doc_references)
                    in_json = False
                    json_buffer = ""  # 重置缓冲区
                except json.JSONDecodeError:
                    # 继续等待后续chunk
                    pass
            else:
                # 纯文本直接处理
                self._stream_output(chunk, stream_callback, full_rsp)
        
        # 处理剩余的不完整JSON（如果有）
        if in_json and json_buffer:
            try:
                json_data = json.loads(json_buffer)
                self._process_json(json_data, stream_callback, full_rsp, doc_references)
            except:
                pass  # 忽略无法解析的残留数据

        # 保存对话历史
        self.messages.append({
            "role": "assistant",
            "content": full_rsp,
            "doc_references": doc_references
        })
        return {"full_rsp": full_rsp, "doc_references": doc_references}

    def _stream_output(self, text: str, callback: Callable, full_rsp: str) -> None:
        """实时输出自然语言文本"""
        if text:
            if callback:
                callback(text)
            full_rsp += text
            print(text, end="", flush=True)

    def _process_json(self, json_data: dict, callback: Callable, full_rsp: str, doc_references: List) -> None:
        """处理解析后的JSON数据"""
        result = json_data.get("result", "").strip()
        refs = json_data.get("doc_references", [])
        
        # 输出JSON中的result字段
        if result:
            if callback:
                callback(result)
            full_rsp += result
            print(result, end="", flush=True)
        
        # 处理文档引用
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except:
                refs = []
        doc_references.extend([ref for ref in refs if ref])  # 去重并过滤空值

# 初始化聊天机器人
if "chatbot" not in st.session_state:
    st.session_state.chatbot = ChatBot(api_key, app_id)

# 显示历史消息
for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("doc_references"):
            show_references(msg["doc_references"])

# 用户输入处理
if prompt := st.chat_input("Ask a question about Dior products..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        current_response = [""]  # 使用列表保持可变状态
        
        def stream_callback(chunk: str) -> None:
            """流式更新界面"""
            current_response[0] += chunk
            message_placeholder.markdown(current_response[0] + "▌")  # 末尾加载符号
        
        try:
            response = st.session_state.chatbot.ask(prompt, stream_callback)
            full_response = response["full_rsp"].replace("▌", "").strip()  # 移除加载符号
            doc_references = response["doc_references"]
            
            # 显示完整响应
            message_placeholder.markdown(full_response)
            
            # 显示文档引用
            if doc_references:
                show_references(doc_references)
            
            # 更新会话历史
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response,
                "doc_references": doc_references
            })
            
        except Exception as e:
            message_placeholder.error(f"⚠️ Error: {str(e)}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Apologies, an error occurred. Please try again later."
            })

# ===== 库存查询模块 =====
with st.sidebar:
    if st.button("📦 Show Stock Query" if not st.session_state.show_stock_query else "❌ Hide Stock Query"):
        st.session_state.show_stock_query = not st.session_state.show_stock_query
        st.rerun()
    if st.session_state.show_stock_query:
        show_stock_query()

    if st.button("🔄 Clear Conversation"):
        st.session_state.messages = [{"role": "assistant", "content": "How can I help you today?"}]
        st.session_state.doc_references = []
        st.session_state.show_stock_query = False
        st.session_state.chatbot = ChatBot(api_key, app_id)
        st.rerun()

    st.divider()
    st.caption("© 2025 Dior Product Assistant")
