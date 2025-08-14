#!/usr/bin/env python3
"""
Plan Review Module for OpenAI Assistants API Integration
Handles uploading plans to assistants and processing review responses
"""

import os
import json
import base64
from typing import Optional, Dict, Any
import udochat
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

def load_reviewers() -> Dict[str, Any]:
    """Load active reviewers configuration"""
    with open('activereviewers.json', 'r') as f:
        return json.load(f)

def get_stormwater_reviewer() -> Optional[Dict[str, str]]:
    """Get the stormwater reviewer configuration"""
    reviewers = load_reviewers()
    for reviewer in reviewers['reviewers']:
        if reviewer['name'] == 'Stormwater Reviewer':
            return reviewer
    return None

def extract_text_with_ocr_blocks(pdf_data):
    """
    Extract text from PDF using Tesseract OCR with block-level detection
    This groups text into larger blocks which might be more useful for document analysis
    
    Args:
        pdf_data (bytes): PDF file content as bytes
        
    Returns:
        list: Array of text blocks with bounding boxes
    """
    try:
        images = convert_from_bytes(pdf_data, dpi=150, fmt='PNG')
        
        ocr_results = []
        
        for page_num, image in enumerate(images, 1):
            # Use Tesseract to get text blocks
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            # Group by block_num to get text blocks
            blocks = {}
            n_boxes = len(data['text'])
            
            for i in range(n_boxes):
                block_num = data['block_num'][i]
                text = data['text'][i].strip()
                
                if text and int(data['conf'][i]) > 30:
                    if block_num not in blocks:
                        blocks[block_num] = {
                            'texts': [],
                            'x_coords': [],
                            'y_coords': [],
                            'widths': [],
                            'heights': [],
                            'confidences': []
                        }
                    
                    blocks[block_num]['texts'].append(text)
                    blocks[block_num]['x_coords'].append(data['left'][i])
                    blocks[block_num]['y_coords'].append(data['top'][i])
                    blocks[block_num]['widths'].append(data['width'][i])
                    blocks[block_num]['heights'].append(data['height'][i])
                    blocks[block_num]['confidences'].append(data['conf'][i])
            
            # Process each block
            for block_num, block_data in blocks.items():
                if block_data['texts']:
                    # Combine all text in the block
                    combined_text = ' '.join(block_data['texts'])
                    
                    # Calculate bounding box for the entire block
                    min_x = min(block_data['x_coords'])
                    min_y = min(block_data['y_coords'])
                    max_x = max([x + w for x, w in zip(block_data['x_coords'], block_data['widths'])])
                    max_y = max([y + h for y, h in zip(block_data['y_coords'], block_data['heights'])])
                    
                    # Average confidence
                    avg_confidence = sum(block_data['confidences']) / len(block_data['confidences'])
                    
                    ocr_result = {
                        "text": combined_text,
                        "bbox": {
                            "x": min_x,
                            "y": min_y,
                            "width": max_x - min_x,
                            "height": max_y - min_y
                        },
                        "page": page_num,
                        "confidence": int(avg_confidence),
                        "block_id": block_num
                    }
                    
                    ocr_results.append(ocr_result)
        
        return ocr_results
        
    except Exception as e:
        print(f"Error during OCR block processing: {e}")
        return []

def format_ocr_for_prompt(ocr_data: list) -> str:
    """
    Format OCR data into a readable string for AI prompt
    
    Args:
        ocr_data: List of OCR results from extract_text_with_ocr_blocks
        
    Returns:
        str: Formatted text for inclusion in AI prompt
    """
    if not ocr_data:
        return "No text extracted from the document."
    
    # Group by page
    pages = {}
    for item in ocr_data:
        page = item['page']
        if page not in pages:
            pages[page] = []
        pages[page].append(item)
    
    formatted_text = []
    formatted_text.append("=== EXTRACTED TEXT FROM PLAN DOCUMENTS: USE ONLY FOR REFERENCE NOT COMMENTS ===\n")
    
    for page_num in sorted(pages.keys()):
        page_blocks = pages[page_num]
        formatted_text.append(f"PAGE {page_num} ({len(page_blocks)} text blocks):")
        formatted_text.append("-" * 40)
        
        # Sort blocks by position (top to bottom, left to right)
        sorted_blocks = sorted(page_blocks, key=lambda x: (x['bbox']['y'], x['bbox']['x']))
        
        for i, block in enumerate(sorted_blocks, 1):
            bbox = block['bbox']
            confidence = block['confidence']
            text = block['text']
            
            # Include position info for the AI to understand layout
            formatted_text.append(
                f"Block {i} [Position: x={bbox['x']}, y={bbox['y']}, "
                f"size={bbox['width']}x{bbox['height']}, confidence={confidence}%]:"
            )
            formatted_text.append(f"  \"{text}\"")
            formatted_text.append("")  # Empty line for readability
        
        formatted_text.append("")  # Extra line between pages
    
    formatted_text.append("=== END EXTRACTED TEXT ===\n")
    
    return "\n".join(formatted_text)

def submit_plan_to_stormwater_reviewer(pdf_data: bytes, title: str) -> Dict[str, Any]:
    """
    Submit a plan (first sheet) to the stormwater reviewer assistant
    
    Args:
        pdf_data: The PDF file content as bytes
        title: The title of the plan
        
    Returns:
        Dict containing the response and metadata
    """
    try:
        # Get stormwater reviewer configuration
        stormwater_reviewer = get_stormwater_reviewer()
        if not stormwater_reviewer:
            return {
                "status": "error",
                "error": "Stormwater reviewer not found in configuration"
            }
        
        # Extract OCR text blocks from the PDF
        print(f"Extracting OCR data for plan review: {title}")
        ocr_data = extract_text_with_ocr_blocks(pdf_data)
        print(f"OCR extraction complete: Found {len(ocr_data)} text blocks")
        
        # Format OCR data for the prompt
        ocr_text = format_ocr_for_prompt(ocr_data)
        
        # Create enhanced message with OCR data
        message = f"""Please review this development plan for stormwater compliance.

Plan Title: {title}

This is the first sheet of the plan set that needs review according to municipal stormwater regulations.

{ocr_text}

Based on the extracted text and layout information above, please provide your review focusing on:
1. Stormwater management requirements
2. Impervious surface calculations and compliance
3. Drainage and erosion control measures
4. UDO Section 9 compliance
5. Any missing information or documentation

When referencing specific areas of concern, use the position information from the extracted text blocks to provide precise feedback."""
        
        # Call the assistant (it already has the proper formatting instructions)
        result = udochat.create_flask_response(
            message=message,
            assistant_id=stormwater_reviewer['assistant_id'],
            thread_id=None  # Create new thread for each review
        )
        
        if result.get('status') == 'success':
            assistant_response = result.get('response', '')
            
            # The assistant should return properly formatted JSON, but let's handle parsing safely
            try:
                # Try to parse the response as JSON
                if assistant_response.strip().startswith('{'):
                    comments_data = json.loads(assistant_response)
                else:
                    # If response doesn't start with JSON, look for JSON within the response
                    start_idx = assistant_response.find('{')
                    end_idx = assistant_response.rfind('}') + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = assistant_response[start_idx:end_idx]
                        comments_data = json.loads(json_str)
                    else:
                        # Fallback: create basic structure
                        comments_data = {
                            "comments": [{
                                "page_key": "Sheet 1",
                                "region": {"x": 0, "y": 0, "w": 100, "h": 100},
                                "body": assistant_response,
                                "suggested_fix": "Please review the assistant's feedback for specific recommendations.",
                                "severity": "major",
                                "category": "stormwater",
                                "code_refs": []
                            }]
                        }
            except json.JSONDecodeError:
                # If JSON parsing fails, create a fallback structure
                comments_data = {
                    "comments": [{
                        "page_key": "Sheet 1",
                        "region": {"x": 0, "y": 0, "w": 100, "h": 100},
                        "body": assistant_response,
                        "suggested_fix": "Please review the assistant's feedback for specific recommendations.",
                        "severity": "major",
                        "category": "stormwater",
                        "code_refs": []
                    }]
                }
            
            return {
                "status": "success",
                "comments_data": comments_data,
                "raw_response": assistant_response,
                "assistant_id": result.get('assistant_id'),
                "thread_id": result.get('thread_id')
            }
        else:
            return {
                "status": "error",
                "error": "Failed to get response from assistant",
                "details": result.get('response', 'Unknown error')
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": "Failed to process plan with AI assistant",
            "details": str(e)
        }

def get_reviewer_by_name(reviewer_name: str) -> Optional[Dict[str, str]]:
    """Get a specific reviewer by name"""
    reviewers = load_reviewers()
    for reviewer in reviewers['reviewers']:
        if reviewer['name'] == reviewer_name:
            return reviewer
    return None

def submit_plan_to_reviewer(pdf_data: bytes, title: str, reviewer_name: str) -> Dict[str, Any]:
    """
    Submit a plan to any specified reviewer
    
    Args:
        pdf_data: The PDF file content as bytes
        title: The title of the plan
        reviewer_name: Name of the reviewer (e.g., "Stormwater Reviewer")
        
    Returns:
        Dict containing the response and metadata
    """
    try:
        # Get reviewer configuration
        reviewer = get_reviewer_by_name(reviewer_name)
        if not reviewer:
            return {
                "status": "error",
                "error": f"Reviewer '{reviewer_name}' not found in configuration"
            }
        
        # Extract OCR text blocks from the PDF
        print(f"Extracting OCR data for {reviewer_name} review: {title}")
        ocr_data = extract_text_with_ocr_blocks(pdf_data)
        print(f"OCR extraction complete: Found {len(ocr_data)} text blocks")
        
        # Format OCR data for the prompt
        ocr_text = "" #format_ocr_for_prompt(ocr_data)
        
        # Create enhanced message with OCR data
        message = f"""Please review this development plan.

Plan Title: {title}

This is the first sheet of the plan set that needs review according to your role.

{ocr_text}

Rely on your file search tool for generating comments. Please provide your review."""
        
        # Call the assistant
        result = udochat.create_flask_response(
            message=message,
            assistant_id=reviewer['assistant_id'],
            thread_id=None  # Create new thread for each review
        )
        
        if result.get('status') == 'success':
            assistant_response = result.get('response', '')
            
            # Try to parse as JSON, fallback to simple structure if needed
            try:
                if assistant_response.strip().startswith('{'):
                    comments_data = json.loads(assistant_response)
                else:
                    start_idx = assistant_response.find('{')
                    end_idx = assistant_response.rfind('}') + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = assistant_response[start_idx:end_idx]
                        comments_data = json.loads(json_str)
                    else:
                        comments_data = {
                            "comments": [{
                                "page_key": "Sheet 1",
                                "region": {"x": 0, "y": 0, "w": 100, "h": 100},
                                "body": assistant_response,
                                "suggested_fix": "Please review the assistant's feedback for specific recommendations.",
                                "severity": "major",
                                "category": reviewer_name.lower().replace(" reviewer", ""),
                                "code_refs": []
                            }]
                        }
            except json.JSONDecodeError:
                comments_data = {
                    "comments": [{
                        "page_key": "Sheet 1",
                        "region": {"x": 0, "y": 0, "w": 100, "h": 100},
                        "body": assistant_response,
                        "suggested_fix": "Please review the assistant's feedback for specific recommendations.",
                        "severity": "major",
                        "category": reviewer_name.lower().replace(" reviewer", ""),
                        "code_refs": []
                    }]
                }
            
            return {
                "status": "success",
                "comments_data": comments_data,
                "raw_response": assistant_response,
                "assistant_id": result.get('assistant_id'),
                "thread_id": result.get('thread_id'),
                "reviewer_name": reviewer_name
            }
        else:
            return {
                "status": "error",
                "error": f"Failed to get response from {reviewer_name}",
                "details": result.get('response', 'Unknown error')
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to process plan with {reviewer_name}",
            "details": str(e)
        }