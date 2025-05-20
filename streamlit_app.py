import streamlit as st
from dashscope import Application
from http import HTTPStatus
import os
import re
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

# 辅助函数 - 显示文档引用（统一逻辑）
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

# 聊天机器人类（完全复用HR Bot的流式逻辑）
class ChatBot:
    def __init__(self, api_key: str, app_id: str):
        self.api_key = api_key
        self.app_id = app_id
        self.messages = []
        self.json_pattern = re.compile(r'({.*?})$', re.DOTALL)  # 匹配末尾JSON

    def ask(self, message: str, stream_callback: Callable[[str], None] = None) -> Dict:
        if len(self.messages) >= 7:
            self.messages.pop(1)
        self.messages.append({"role": "user", "content": message})
        
        full_rsp = ""
        doc_references = []
        responses = Application.call(
            api_key=self.api_key,
            app_id=self.app_id,
            messages=self.messages,
            prompt=message,
            stream=True,
            flow_stream_mode="agent_format",
            incremental_output=True
        )

        for response in responses:
            if response.status_code != HTTPStatus.OK:
                print(f"API Error: {response.message}")
                continue
            
            output_text = response.output.text or ""
            match = self.json_pattern.search(output_text)
            
            if match:
                # 分离自然语言和JSON
                natural_text = output_text[:match.start()].strip()
                json_str = output_text[match.start():]
                
                # 先流式输出自然语言
                if natural_text:
                    self._stream_update(stream_callback, natural_text, full_rsp)
                
                # 解析JSON
                try:
                    json_data = json.loads(json_str)
                    result = json_data.get("result", "").strip()
                    refs = json_data.get("doc_references", [])
                    
                    # 输出JSON中的结果
                    if result:
                        self._stream_update(stream_callback, result, full_rsp)
                    
                    # 处理引用
                    if isinstance(refs, str):
                        refs = json.loads(refs) if refs else []
                    doc_references.extend(refs)
                    
                except json.JSONDecodeError:
                    # 若JSON不完整，忽略并继续（由后续chunk补全）
                    full_rsp += output_text
                    if stream_callback:
                        stream_callback(output_text)
            else:
                # 纯文本直接流式输出
                self._stream_update(stream_callback, output_text, full_rsp)
        
        # 清理残留符号
        full_rsp = re.sub(r'[{}"\n]', '', full_rsp.strip())
        self.messages.append({
            "role": "assistant",
            "content": full_rsp,
            "doc_references": doc_references
        })
        return {"full_rsp": full_rsp, "doc_references": doc_references}

    def _stream_update(self, callback: Callable, text: str, full_rsp: str) -> None:
        """实时更新界面和完整响应"""
        if text and callback:
            callback(text)
        full_rsp += text
        print(text, end="", flush=True)

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

# 用户输入处理（流式回调绑定）
if prompt := st.chat_input("Ask a question about Dior products..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        current_text = [""]  # 使用列表保持可变状态
        
        def stream_callback(chunk: str) -> None:
            """实时更新界面，追加内容并显示加载符号"""
            current_text[0] += chunk
            message_placeholder.markdown(current_text[0] + "▌")
        
        try:
            response = st.session_state.chatbot.ask(prompt, stream_callback)
            full_response = response["full_rsp"].replace("▌", "").strip()  # 移除加载符号
            doc_references = response["doc_references"]
            
            # 显示完整响应和引用
            message_placeholder.markdown(full_response)
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
                "content": "Sorry, an error occurred. Please try again later."
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
