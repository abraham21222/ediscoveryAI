# Parallel AI Analysis Function - TO BE INTEGRATED

def process_custom_ai_analysis_parallel(job_id, document_ids, custom_prompt, create_tags=True, redaction_mode=False, redaction_prompt=''):
    """
    Process documents with custom AI prompt using PARALLEL PROCESSING with Grok 4 Fast.
    Up to 17x faster than sequential processing!
    """
    import os
    import sys
    import re
    from openai import OpenAI
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    import psycopg2
    import psycopg2.extras
    
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"🚀 PARALLEL AI ANALYSIS JOB {job_id}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"📄 Documents: {len(document_ids)}", file=sys.stderr)
    print(f"⚡ Model: x-ai/grok-4-fast (ULTRA-FAST MODE)", file=sys.stderr)
    print(f"🔀 Parallel Workers: {min(10, len(document_ids))}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    sys.stderr.flush()
    
    try:
        # Initialize OpenAI client (shared across threads - thread-safe)
        api_key = os.environ.get('OPENROUTER_API_KEY')
        if not api_key:
            print("❌ Error: OPENROUTER_API_KEY not set", file=sys.stderr)
            custom_ai_progress[job_id]['completed'] = True
            return
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        
        # Thread-safe lock for progress updates
        progress_lock = threading.Lock()
        
        def analyze_single_document(doc_id):
            """Analyze a single document - called in parallel for each document."""
            conn = None
            try:
                # Each thread gets its own database connection (thread-safe)
                conn = psycopg2.connect(
                    host=os.environ.get("POSTGRES_HOST", os.environ.get("DB_HOST", "localhost")),
                    port=int(os.environ.get("POSTGRES_PORT", os.environ.get("DB_PORT", "5432"))),
                    database=os.environ.get("POSTGRES_DATABASE", os.environ.get("DB_NAME", "ediscovery_metadata")),
                    user=os.environ.get("POSTGRES_USER", os.environ.get("DB_USER", "abrahambloom")),
                    password=os.environ.get("POSTGRES_PASSWORD", os.environ.get("DB_PASSWORD", ""))
                )
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Update progress (thread-safe)
                with progress_lock:
                    custom_ai_progress[job_id]['current_document'] = doc_id
                
                # Get document content
                cursor.execute("""
                    SELECT d.document_id, d.subject, d.body_text
                    FROM documents d
                    WHERE d.document_id = %s
                """, (doc_id,))
                
                doc = cursor.fetchone()
                if not doc:
                    print(f"⚠️  Document {doc_id} not found", file=sys.stderr)
                    return None
                
                # Update progress with subject (thread-safe)
                with progress_lock:
                    custom_ai_progress[job_id]['current_subject'] = doc['subject']
                
                print(f"🔍 Analyzing: {doc['subject'][:60]}...", file=sys.stderr)
                sys.stderr.flush()
                
                # Prepare content for AI
                content = f"Subject: {doc['subject']}\n\nBody:\n{doc['body_text'] or 'No content'}"
                
                # Call AI with enhanced prompt for structured output
                structured_prompt = f"""{custom_prompt}

Please provide your analysis in this format:
RELEVANCE: [score 0-100]
PRIVILEGE_RISK: [score 0-100, likelihood this is attorney-client privileged communication]
CLASSIFICATION: [relevant/not-relevant/needs-review]
KEY FINDINGS: [bullet points of key findings]
ANALYSIS: [your detailed analysis]"""
                
                response = client.chat.completions.create(
                    model="x-ai/grok-4-fast",  # GROK 4 FAST - ULTRA-SPEED!
                    messages=[
                        {"role": "system", "content": structured_prompt},
                        {"role": "user", "content": content}
                    ],
                    max_tokens=700,
                    temperature=0.3
                )
                
                ai_response = response.choices[0].message.content
                
                # Parse the structured response
                relevance_match = re.search(r'RELEVANCE:\s*(\d+)', ai_response, re.IGNORECASE)
                relevance_score = int(relevance_match.group(1)) if relevance_match else 50
                
                privilege_match = re.search(r'PRIVILEGE[_\s]*RISK:\s*(\d+)', ai_response, re.IGNORECASE)
                privilege_risk = int(privilege_match.group(1)) if privilege_match else 0
                
                classification_match = re.search(r'CLASSIFICATION:\s*(\S+)', ai_response, re.IGNORECASE)
                classification = classification_match.group(1) if classification_match else 'needs-review'
                
                findings_match = re.search(r'KEY FINDINGS:\s*(.+?)(?=ANALYSIS:|$)', ai_response, re.IGNORECASE | re.DOTALL)
                key_findings = findings_match.group(1).strip() if findings_match else ''
                
                # Extract topics/tags from the analysis
                topics = []
                if 'fraud' in ai_response.lower() or 'fraud' in custom_prompt.lower():
                    topics.append('Financial Fraud')
                if 'privilege' in ai_response.lower() or 'attorney' in ai_response.lower():
                    topics.append('Attorney-Client')
                if 'compliance' in ai_response.lower() or 'regulatory' in ai_response.lower():
                    topics.append('Compliance')
                
                # Save to ai_analysis table
                cursor.execute("""
                    INSERT INTO ai_analysis (
                        document_id, ai_summary, ai_relevance, ai_classification,
                        ai_topics, ai_analyzed_at, privilege_risk
                    ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    ON CONFLICT (document_id)
                    DO UPDATE SET
                        ai_summary = EXCLUDED.ai_summary,
                        ai_relevance = EXCLUDED.ai_relevance,
                        ai_classification = EXCLUDED.ai_classification,
                        ai_topics = EXCLUDED.ai_topics,
                        ai_analyzed_at = CURRENT_TIMESTAMP,
                        privilege_risk = EXCLUDED.privilege_risk
                """, (
                    doc_id,
                    key_findings[:500] if key_findings else ai_response[:500],
                    relevance_score,
                    classification,
                    topics[:3] if topics else None,
                    privilege_risk
                ))
                
                # Also store full analysis in user_review notes
                cursor.execute("""
                    INSERT INTO user_review (document_id, review_notes, review_status)
                    VALUES (%s, %s, 'reviewed')
                    ON CONFLICT (document_id)
                    DO UPDATE SET
                        review_notes = CASE
                            WHEN user_review.review_notes IS NULL THEN EXCLUDED.review_notes
                            ELSE user_review.review_notes || E'\n\n--- Custom AI Analysis ---\n' || EXCLUDED.review_notes
                        END,
                        reviewed_at = CURRENT_TIMESTAMP
                """, (doc_id, f"Custom Analysis:\n{ai_response}"))
                
                conn.commit()
                
                # Create tags if requested
                if create_tags:
                    tags_to_create = []
                    
                    if classification == 'relevant':
                        tags_to_create.append('AI: Relevant')
                    elif classification == 'not-relevant':
                        tags_to_create.append('AI: Not Relevant')
                    else:
                        tags_to_create.append('AI: Needs Review')
                    
                    if relevance_score >= 70:
                        tags_to_create.append('High Priority')
                    elif relevance_score >= 40:
                        tags_to_create.append('Medium Priority')
                    else:
                        tags_to_create.append('Low Priority')
                    
                    for topic in topics:
                        tags_to_create.append(topic)
                    
                    for tag_name in tags_to_create:
                        try:
                            cursor.execute("""
                                INSERT INTO user_tags (document_id, tag_name)
                                VALUES (%s, %s)
                                ON CONFLICT (document_id, tag_name) DO NOTHING
                            """, (doc_id, tag_name))
                        except Exception as tag_error:
                            print(f"⚠️  Could not create tag '{tag_name}': {tag_error}", file=sys.stderr)
                    
                    conn.commit()
                
                # Perform redaction if requested
                redacted_subject = None
                redacted_body = None
                redaction_details = None
                
                if redaction_mode and redaction_prompt:
                    print(f"🔒 Redacting: {doc_id}...", file=sys.stderr)
                    
                    redaction_system_prompt = f"""{redaction_prompt}

Please identify ALL content that matches the redaction criteria and provide:
1. A list of what needs to be redacted with specific instances
2. The redacted subject line (if applicable)
3. The redacted body text with replacements like [REDACTED - SSN], [REDACTED - NAME], etc.

Format your response as:
REDACTION_SUMMARY: [brief summary of what was redacted]
REDACTED_SUBJECT: [redacted subject line]
REDACTED_BODY: [full body text with redactions applied]"""
                    
                    redaction_content = f"SUBJECT: {doc['subject']}\n\nBODY:\n{doc['body_text']}"
                    
                    redaction_response = client.chat.completions.create(
                        model="x-ai/grok-4-fast",  # ALSO USE GROK FOR REDACTION!
                        messages=[
                            {"role": "system", "content": redaction_system_prompt},
                            {"role": "user", "content": redaction_content}
                        ],
                        max_tokens=1500,
                        temperature=0.1
                    )
                    
                    redaction_result = redaction_response.choices[0].message.content
                    
                    summary_match = re.search(r'REDACTION_SUMMARY:\s*(.+?)(?=REDACTED_SUBJECT:|$)', redaction_result, re.IGNORECASE | re.DOTALL)
                    redaction_details = summary_match.group(1).strip() if summary_match else "Redactions applied"
                    
                    subject_match = re.search(r'REDACTED_SUBJECT:\s*(.+?)(?=REDACTED_BODY:|$)', redaction_result, re.IGNORECASE | re.DOTALL)
                    redacted_subject = subject_match.group(1).strip() if subject_match else doc['subject']
                    
                    body_match = re.search(r'REDACTED_BODY:\s*(.+?)$', redaction_result, re.IGNORECASE | re.DOTALL)
                    redacted_body = body_match.group(1).strip() if body_match else doc['body_text']
                    
                    # Store redacted version (thread-safe)
                    with progress_lock:
                        custom_ai_progress[job_id]['redactions'].append({
                            'document_id': doc_id,
                            'original_subject': doc['subject'],
                            'original_body': doc['body_text'],
                            'redacted_subject': redacted_subject,
                            'redacted_body': redacted_body,
                            'redaction_summary': redaction_details
                        })
                
                # Store result for summary (thread-safe)
                result_data = {
                    'document_id': doc_id,
                    'subject': doc['subject'],
                    'relevance': relevance_score,
                    'privilege_risk': privilege_risk,
                    'classification': classification,
                    'key_findings': key_findings[:200] if key_findings else ai_response[:200]
                }
                
                if redaction_mode:
                    result_data['redacted'] = True
                    result_data['redaction_summary'] = redaction_details
                
                with progress_lock:
                    custom_ai_progress[job_id]['results'].append(result_data)
                    custom_ai_progress[job_id]['processed'] += 1
                
                print(f"✅ Completed: {doc['subject'][:60]}...", file=sys.stderr)
                sys.stderr.flush()
                
                return result_data
                
            except Exception as e:
                print(f"❌ Error processing {doc_id}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()
                return None
            finally:
                if conn:
                    conn.close()
        
        # Execute all document analyses in parallel!
        max_workers = min(10, len(document_ids))  # Max 10 parallel threads
        print(f"🚀 Starting parallel processing with {max_workers} workers...\n", file=sys.stderr)
        sys.stderr.flush()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all documents for parallel processing
            future_to_doc = {executor.submit(analyze_single_document, doc_id): doc_id 
                            for doc_id in document_ids}
            
            # Wait for all to complete
            for future in as_completed(future_to_doc):
                doc_id = future_to_doc[future]
                try:
                    result = future.result()
                except Exception as e:
                    print(f"❌ Future exception for {doc_id}: {e}", file=sys.stderr)
        
        # Mark as completed
        custom_ai_progress[job_id]['completed'] = True
        
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"✅ JOB COMPLETE: {custom_ai_progress[job_id]['processed']}/{custom_ai_progress[job_id]['total']} documents", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.stderr.flush()
        
    except Exception as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"❌ FATAL ERROR in job {job_id}", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.stderr.flush()
        custom_ai_progress[job_id]['completed'] = True

