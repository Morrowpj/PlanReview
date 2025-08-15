#!/usr/bin/env python3
"""
OpenAI Responses API Integration Script
Simple script to send requests to OpenAI's Responses API and get responses with file support
"""

import os
import json
import base64
from openai import OpenAI
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import time
from PIL import Image
from io import BytesIO
import pymupdf as fitz  # PyMuPDF

load_dotenv('.env')

def ensure_bytes(data):
    if isinstance(data, memoryview):
        return data.tobytes()
    elif isinstance(data, bytearray):
        return bytes(data)
    elif hasattr(data, 'read'):  # file-like object
        return data.read()
    return data  # already bytes

class OpenAIResponses:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OpenAI client for Responses API"""
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        self.conversation_history = []
    
    def send_to_responses_api(self, message: str, prompt_id: str, conversation_id: Optional[str] = None, 
                            file_data: Optional[bytes] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """Send message to OpenAI Responses API with direct PDF file input"""
        try:
            prompt_text = """
Role and Objective

You are a specialized technical QA assistant focused on reviewing CAD sheet setup and plotting compliance for civil engineering and land development plan sets.

Checklist: (1) Analyze provided PDF for sheet setup and plotting compliance, (2) Identify and validate comments only for designated grading plan elements and labels, (3) Apply all exclusion rules and prohibited element filters, (4) Compile findings as a numbered, structured list.

Instructions

- You will be provided with a PDF representing a single sheet from a larger development set.
- Only evaluate CAD setup, plotting, and drafting presentation—do not address design or engineering accuracy.

Sub-categories

Review protocol:
- Do not comment on:
    - Elements with (typ.) labels repeated once or twice.
    - Missing labels if leaders/annotations are present near the object.
    - Rim labels absent when data is found in a drainage or utility table.
    - Features with leaders or arrows pointing to them (consider these adequately labeled).
- Recognize that 'screened' means 'grayed back'—if linework appears lighter (grayer) than others, it is considered screened.

Primary Focus Elements

Concentrate comments only on the following grading plan elements and their labels:
- Grading Plan components: existing/proposed underground utilities, storm drainage (mains, pipes, structures in standard layers), roof drainage, topographic info (with labels), existing tree line, accessible parking hatching, property boundary, water mains/valves/hydrants/BFPs (screened), sanitary sewer mains/manholes (screened), benchmarks, building/pavement footprints, grade break lines, flow arrows, permanent ditch/liner labels, drainage schedules/tables/gasketed pipes, outlet protection tables, spot elevation plans, culvert crossings/details/sequences.
- Grading Plan-specific labels: top/bottom of curb elevations, single spot elevations at critical locations, top/bottom of wall (ground elevations only), proposed building FFEs, stem walls, spot elevations at quarter points/high points on intersections and cul-de-sacs.
- Storm Drainage-specific labels: structure invert (and upstream structure), T/C (curb inlet), T/G (drop/yard inlets), RIM (inlets/junction boxes), weir elevations, road stations, pipe labels (length/material/slope), roof drainage, culvert data (size, slope, material, number, burial depth, true/buried inverts), existing pipes/structures being extended or adjusted, elevations at utility crossings, stream buffer zones if grading into buffer, spot grades at parking corners/critical points, and Outlet Structure information from any SCM.

Additional Considerations:
- Omit curb/gutter spot grades where an inlet is present; use T/C data from drainage.
- If a drainage table is required, data must also be called out directly at each structure/pipe.
- On plan/profile sheets, exclude structure data for non-profiled roads.
- Consider simple typical sections (swales, etc.) for clarity.
- Contour Label clarity, or lack thereof of contour labels.

Prohibited elements (comment if shown on Grading/Storm Drainage Plan):
- Sanitary sewer outfall stationing
- Lot setbacks
- Curb and gutter labels
- “Site Plan” dimensions
- Sidewalk labels
- Accessible ramp labels
- Bearings/distances on property lines
- Tangent/curve data for road/parking centerlines

Do not comment on:
- Engineering calculations or dimensional accuracy
- Design feasibility or code compliance
- Minor cosmetic issues that do not affect plot clarity

Context

- Review is limited to issues explicit and observable in the provided PDF sheet.
- Additional details may appear in associated tables on the sheet.

Reasoning Steps

- Always search for labels/leaders near questionable features before noting missing information.
- Use visual evidence only (no speculation), and be thorough with direct observations.
- For each noted issue, briefly document your reasoning: describe the logical steps and visual cues that led to the identification of the issue, ensuring that each comment reflects this step-by-step reasoning process.

Output Format

# Output Format
Numbered list of comments. Each comment must include:
  1. Issue Category (e.g., Text Overlap, Lineweight, Missing Label)
  2. Brief problem description
  3. Location identified by X/Y coordinates and a bounding box
  4. Reasoning: Succinctly document the logical, observable rationale for the comment, tied to visible PDF evidence
Example:
1. Issue Category: Missing Label
   Problem: No pipe label provided for storm drainage crossing
   Location: X: 212, Y: 415, Bounding Box: [200, 410, 230, 435]
   Reasoning: Examined the area around the pipe; no label or leader was observed near the crossing, and no reference to this feature exists in adjacent tables.

- Ensure accuracy in bounding box placement for clear identification.
- Reason by text as appropriate for comprehensive review.

After all comments, validate that output strictly matches the required format and revise if discrepancies or omissions are found.

Tone

Use an objective, precise, and concise professional drafting review style. Only cite visible, verifiable issues—do not speculate.
            """
            
            # Prepare content for user role
            user_content = [
                {"type": "input_text", "text": "Please review this plan sheet, for reference on comment placement coordinates: The upper left of the PDF is 0,0 and the bottom right is H,W in pixels"}
            ]
            
            # Add file if provided
            if file_data and filename:
                print(f"📁 Converting PDF to high-resolution PNG: {filename}")
                file_data = file_data.tobytes()
                image_data = convert_pdf_to_high_res_image(file_data)
                b64_image = base64.b64encode(image_data).decode('utf-8')
                user_content.append({
                    "type": "input_image", 
                    "image_url": f"data:image/png;base64,{b64_image}",
                })
                print(f"✅ High-resolution PNG added to request")
            
            # Call the Responses API with the new structure
            response = self.client.responses.create(
                model="gpt-5",
                input=[
                    {"role": "developer", "content": [{"type": "input_text", "text": prompt_text}]},
                    {"role": "user", "content": user_content}
                ],
                text={
                    "format": {
                    "type": "json_schema",
                    "name": "comments",
                    "strict": False,
                    "schema": {
                        "type": "object",
                        "properties": {
                        "reasoning": { "type": "string" },
                        "comments": {
                            "type": "array",
                            "items": {
                            "type": "object",
                            "required": [
                                "page_key",
                                "body",
                                "severity",
                                "category"
                            ],
                            "properties": {
                                "reasoning": {
                                "type": "string",
                                "items": {
                                    "type": "string"
                                }
                                },
                                "page_key": {
                                "type": "string"
                                },
                                "region": {
                                "type": "object",
                                "properties": {
                                    "x": {
                                    "type": "number"
                                    },
                                    "y": {
                                    "type": "number"
                                    },
                                    "w": {
                                    "type": "number"
                                    },
                                    "h": {
                                    "type": "number"
                                    }
                                }
                                },
                                "body": {
                                "type": "string"
                                },
                                "suggested_fix": {
                                "type": "string"
                                },
                                "severity": {
                                "enum": [
                                    "info",
                                    "minor",
                                    "major",
                                    "blocking"
                                ]
                                },
                                "category": {
                                "enum": [
                                    "zoning",
                                    "utilities",
                                    "stormwater",
                                    "transportation",
                                    "fire",
                                    "landscape",
                                    "ada",
                                    "general"
                                ]
                                },
                                "code_refs": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                                }
                            }
                            }
                        }
                        },
                        "required": []
                    }
                    },
                    "verbosity": "medium"
                },
                reasoning={
                    "effort": "medium"
                },
                tools=[],
                store=True
                )
            
            return {
                "status": "success",
                "response": response.output_text if hasattr(response, 'output_text') else str(response),
                "prompt_id": prompt_id,
                "conversation_id": conversation_id,
                "usage": response.usage if hasattr(response, 'usage') else None
            }
            
        except Exception as e:
            print(f"❌ Error with Responses API: {e}")
            return {
                "status": "error",
                "response": f"Error: {str(e)}",
                "prompt_id": prompt_id,
                "conversation_id": conversation_id
            }
    
    def send_message(self, message: str, prompt_id: str, conversation_id: Optional[str] = None, 
                    file_data: Optional[bytes] = None, filename: Optional[str] = None) -> str:
        """Send a message using the Responses API and get the response"""
        result = self.send_to_responses_api(message, prompt_id, conversation_id, file_data, filename)
        return result.get("response", "Error: No response received")
    
    def chat_session(self, prompt_id: str, conversation_id: Optional[str] = None):
        """Interactive chat session using Responses API"""
        print("🚀 Starting OpenAI Responses API Chat Session")
        print("Type 'quit' or 'exit' to end the session\n")
        
        current_conversation_id = conversation_id
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                result = self.send_to_responses_api(user_input, prompt_id, current_conversation_id)
                if result["status"] == "success":
                    print(f"\nAssistant: {result['response']}\n")
                    current_conversation_id = result.get("conversation_id")
                else:
                    print(f"\nError: {result['response']}\n")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error in chat session: {e}")


# Flask Integration Functions
def create_flask_response(message: str, prompt_id: str = None, conversation_id: str = None, file_data: bytes = None, filename: str = None) -> dict:
    """Function specifically for Flask integration using Responses API"""
    responses = OpenAIResponses()
    
    if not prompt_id:
        return {
            "response": "Error: prompt_id is required",
            "prompt_id": None,
            "conversation_id": None,
            "status": "error"
        }
    
    result = responses.send_to_responses_api(message, prompt_id, conversation_id, file_data, filename)
    
    return {
        "response": result.get("response", "Error: No response received"),
        "prompt_id": result.get("prompt_id"),
        "conversation_id": result.get("conversation_id"),
        "status": result.get("status", "error")
    }


# Example Flask route (add this to your Flask app)
"""
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    assistant_id = data.get('assistant_id')
    thread_id = data.get('thread_id')
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    try:
        result = create_flask_response(message, assistant_id, thread_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
"""


def main():
    """Main function for testing"""
    # Make sure to set your OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Please set your OPENAI_API_KEY environment variable")
        print("   You can get one from: https://platform.openai.com/api-keys")
        return
    
    # Example usage - you'll need to provide actual prompt_id
    responses = OpenAIResponses()
    
    # You'll need to replace 'your-prompt-id' with an actual prompt ID
    prompt_id = input("Enter your prompt ID: ").strip()
    if not prompt_id:
        print("❌ Prompt ID is required")
        return
    
    # Option 1: Interactive chat session
    responses.chat_session(prompt_id)
    
    # Option 2: Single message (uncomment to use)
    # result = responses.send_to_responses_api("Hello! Can you help me with Python programming?", prompt_id)
    # print(f"Response: {result['response']}")

def convert_pdf_to_high_res_image(pdf_bytes):
    """
    Helper function to convert PDF to high-resolution RGB image and return as PNG bytes
    """
    try:
        # Open PDF document
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Check if document is encrypted or protected
        if doc.needs_pass:
            print("PDF is password protected, returning original")
            doc.close()
            return pdf_bytes
            
        if doc.is_closed:
            print("PDF document is closed, returning original")
            return pdf_bytes
        
        # Get first page (assuming single page for plan review)
        page = doc[0]
        
        # Render page as high-resolution RGB image
        mat = fitz.Matrix(4, 4)  # 4x scaling for much better quality
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        
        # Convert to PNG bytes
        img_bytes = pix.tobytes("png")
        
        # Clean up
        pix = None
        doc.close()
        
        print(f"✅ PDF converted to high-resolution PNG image (estimated size: {len(img_bytes)} bytes)")
        return img_bytes
        
    except Exception as e:
        print(f"Error converting PDF to high-resolution image: {e}")
        # Return original bytes if conversion fails
        return pdf_bytes

if __name__ == "__main__":
    main()