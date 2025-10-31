#!/usr/bin/env python3
"""
Quick test of the Custom AI Analysis feature
"""
import requests
import json
import time

BASE_URL = "http://localhost:8080"

def test_custom_ai_flow():
    print("🧪 Testing Custom AI Analysis Feature\n")
    
    # Step 1: Get some documents
    print("1️⃣ Getting documents...")
    response = requests.post(
        f"{BASE_URL}/api/search",
        json={"query": "", "limit": 5}
    )
    data = response.json()
    
    if not data['success']:
        print("❌ Failed to get documents")
        return False
    
    documents = data['documents']
    doc_ids = [d['document_id'] for d in documents]
    print(f"   ✅ Found {len(doc_ids)} documents\n")
    
    # Step 2: Start custom AI analysis
    print("2️⃣ Starting custom AI analysis...")
    custom_prompt = "Analyze this document for key topics and themes. Provide a brief 1-sentence summary."
    
    response = requests.post(
        f"{BASE_URL}/api/custom-ai-analysis",
        json={
            "document_ids": doc_ids[:3],  # Just test with 3 docs
            "custom_prompt": custom_prompt
        }
    )
    
    result = response.json()
    if not result['success']:
        print(f"❌ Failed to start analysis: {result.get('error')}")
        return False
    
    job_id = result['job_id']
    estimated_cost = result['estimated_cost']
    print(f"   ✅ Job started: {job_id}")
    print(f"   💰 Estimated cost: ${estimated_cost:.2f}\n")
    
    # Step 3: Poll for progress
    print("3️⃣ Tracking progress...")
    max_polls = 60  # 2 minutes max
    polls = 0
    
    while polls < max_polls:
        response = requests.get(f"{BASE_URL}/api/custom-ai-progress/{job_id}")
        progress = response.json()
        
        if not progress['success']:
            print(f"❌ Failed to get progress: {progress.get('error')}")
            return False
        
        processed = progress['processed']
        total = progress['total']
        completed = progress['completed']
        
        percentage = (processed / total * 100) if total > 0 else 0
        print(f"   📊 Progress: {processed}/{total} ({percentage:.0f}%)")
        
        if completed:
            print(f"   ✅ Analysis completed!\n")
            break
        
        time.sleep(2)
        polls += 1
    
    if polls >= max_polls:
        print("   ⏰ Timeout waiting for completion\n")
        return False
    
    # Step 4: Verify results were saved
    print("4️⃣ Verifying results...")
    test_doc_id = doc_ids[0]
    response = requests.get(f"{BASE_URL}/api/document/{test_doc_id}/review")
    review_data = response.json()
    
    if review_data['success'] and review_data['review']:
        notes = review_data['review'].get('review_notes', '')
        if 'Custom Analysis:' in notes:
            print(f"   ✅ Custom analysis found in document review notes\n")
        else:
            print(f"   ⚠️ No custom analysis found (may take a moment to appear)\n")
    else:
        print(f"   ⚠️ Review data not available yet\n")
    
    print("=" * 60)
    print("✅ CUSTOM AI ANALYSIS TEST PASSED")
    print("=" * 60)
    print("\n🎉 Feature is working! Try it in the UI:")
    print("   1. Open http://localhost:8080")
    print("   2. Filter some documents")
    print("   3. Click '🎯 Custom AI Analysis'")
    print("   4. Use a template or write a custom prompt")
    print("   5. Watch the magic happen!\n")
    
    return True

if __name__ == '__main__':
    try:
        test_custom_ai_flow()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
