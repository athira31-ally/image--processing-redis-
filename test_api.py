#!/usr/bin/env python3
"""
Simple test script for the Image Processing API
"""
import requests
import time
import json
from pathlib import Path

API_BASE = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    response = requests.get(f"{API_BASE}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_upload_and_process():
    """Test image upload and processing"""
    print("\n📸 Testing image upload and processing...")
    
    # Create a simple test image if it doesn't exist
    test_image_path = "test_image.jpg"
    if not Path(test_image_path).exists():
        print("Creating test image...")
        from PIL import Image
        img = Image.new('RGB', (400, 300), color='lightblue')
        img.save(test_image_path)
    
    # Upload image
    print("Uploading image...")
    with open(test_image_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{API_BASE}/upload", files=files)
    
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        return False
    
    upload_result = response.json()
    file_id = upload_result['file_id']
    print(f"✅ Upload successful! File ID: {file_id}")
    
    # Process image (resize)
    print("Processing image (resize to 200x150)...")
    params = {
        'operation': 'resize',
        'width': 200,
        'height': 150
    }
    response = requests.post(f"{API_BASE}/process/{file_id}", params=params)
    
    if response.status_code != 200:
        print(f"❌ Processing failed: {response.text}")
        return False
    
    process_result = response.json()
    processing_id = process_result['processing_id']
    print(f"✅ Processing started! Processing ID: {processing_id}")
    
    # Check status
    print("Checking processing status...")
    for i in range(10):  # Wait up to 10 seconds
        response = requests.get(f"{API_BASE}/status/{processing_id}")
        
        if response.status_code != 200:
            print(f"❌ Status check failed: {response.text}")
            return False
        
        status_result = response.json()
        status = status_result['status']
        print(f"Status: {status}")
        
        if status == 'completed':
            print("✅ Processing completed!")
            
            # Try to download result
            print("Downloading processed image...")
            response = requests.get(f"{API_BASE}/download/{processing_id}")
            if response.status_code == 200:
                with open(f"processed_{processing_id}.jpg", 'wb') as f:
                    f.write(response.content)
                print("✅ Download successful!")
                return True
            else:
                print(f"❌ Download failed: {response.text}")
                return False
        
        elif status == 'failed':
            print(f"❌ Processing failed: {status_result.get('result', {})}")
            return False
        
        time.sleep(1)
    
    print("❌ Processing timeout")
    return False

def main():
    """Run all tests"""
    print("🧪 Image Processing API Test Suite")
    print("=" * 40)
    
    # Test health
    if not test_health():
        print("❌ Health check failed!")
        return
    
    # Test upload and processing
    if not test_upload_and_process():
        print("❌ Upload/processing test failed!")
        return
    
    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    main()
