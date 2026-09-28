
import streamlit as st
import requests
st.set_page_config(page_title="AFL Assistant", page_icon="🏉")
st.title("AFL Assistant")
st.caption("Domain-locked AFL chat + retrieval + prediction demo")
if "cid" not in st.session_state: st.session_state.cid="demo"
if "messages" not in st.session_state: st.session_state.messages=[]
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.write(m["content"])
q=st.chat_input("Ask an AFL question...")
if q:
    st.session_state.messages.append({"role":"user","content":q})
    try:
        r=requests.post("http://127.0.0.1:8000/chat",json={"message":q,"conversation_id":st.session_state.cid},timeout=8)
        data=r.json()
        ans=data["response"]
    except Exception as e:
        ans=f"API error: {e}"
    st.session_state.messages.append({"role":"assistant","content":ans})
    st.rerun()
