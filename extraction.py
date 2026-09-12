import base64
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from models import State, ReceiptData

def extraction_node(state: State) -> dict:
    """
    Extraction node logic (Vision LLM call).
    Reads the receipt image and extracts structured data.
    """
    image_path = state.get("image_path", "")
    note = state.get("employee_note", "")
    retries = state.get("extraction_retries", 0)
    
    image_data = ""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
            
    # Initialize the LLM with structured output
    llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0).with_structured_output(ReceiptData)
    
    message_content = [
        {
            "type": "text", 
            "text": (
                "Extract the receipt data from the provided image. "
                f"The employee also included this note: '{note}'. "
                "If the image is blurry, output a low confidence_score."
            )
        }
    ]
    
    if image_data:
        # Pass image to multimodal model
        message_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
        })
    else:
        raise ValueError(f"Image not found at path: {image_path}")

    msg = HumanMessage(content=message_content)
    
    try:
        data = llm.invoke([msg])
    except Exception as e:
        print(f"Extraction LLM call failed: {e}")
        data = None

    return {
        "receipt_data": data,
        "extraction_retries": retries + 1
    }
