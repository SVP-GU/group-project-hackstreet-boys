#testa streamlit
import streamlit as st

st.title("Hej och välkommen <3")
namn = st.text_input("Vad heter du?")

if namn:
    st.write(f"Hej {namn}!!!!")
