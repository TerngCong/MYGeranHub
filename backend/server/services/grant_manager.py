from jamaibase import JamAI, types as p
from typing import Dict, Any, Optional
from ..core.config import settings
from datetime import datetime

class GrantAgent:
    def __init__(self):
        self.project_id = settings.jamai_project_id
        self.api_key = settings.jamai_api_key
        
        # Handle base_url to prevent double versioning (SDK adds /v2)
        base_url = settings.jamai_base_url.rstrip("/") if settings.jamai_base_url else None
        if base_url:
            if base_url.endswith("/v2"):
                base_url = base_url[:-3]
            elif base_url.endswith("/v1"):
                base_url = base_url[:-3]
        
        self.base_url = base_url
        
        if not all([self.project_id, self.api_key, self.base_url]):
             raise RuntimeError("JamAI configuration missing for GrantAgent.")

        self.client = JamAI(
            project_id=self.project_id,
            token=self.api_key,
            api_base=self.base_url
        )
        
        # Table IDs
        self.table_1_id = "First_Grant"
        self.table_guard_id = "Input_Guardrail"
        self.table_2_id = "Final_Grant"

    def process_input(self, session_state: Dict[str, Any], new_input: str) -> Dict[str, Any]:
        """
        Processes user input through the Three-Stage Agent workflow.
        """
        # 0. Get Context
        current_buffer = session_state.get("buffer", "")
        last_question = session_state.get("last_question", "What is your business profile?") # Default if none

        # Helper to safely get text content from column response
        def get_col_text(col_data):
            if col_data is None:
                return ""
            if hasattr(col_data, "text"):
                return col_data.text
            if isinstance(col_data, dict) and "value" in col_data:
                return str(col_data["value"])
            if hasattr(col_data, "choices") and col_data.choices:
                return col_data.choices[0].message.content
            return str(col_data)

        # 1. Logic Split: First Input vs Follow-up
        # If buffer is empty, it's the first input (redirected from Chat Table).
        # We skip the Guardrail and go straight to the Detective.
        
        if not current_buffer:
            # --- FIRST INPUT PATH ---
            updated_buffer = f"User: {new_input}".strip()
            session_state["buffer"] = updated_buffer
            
            # Proceed to call Detective (Step 3 logic)
            # We can skip the Guardrail block and fall through to Step 3
            pass
            
        else:
            # --- FOLLOW-UP PATH (Guardrail Active) ---
            # Call Input Guardrail (Check if the new input is valid/relevant to the last question)
            try:
                completion_guard = self.client.table.add_table_rows(
                    "action",
                    p.RowAddRequest(
                        table_id=self.table_guard_id,
                        data=[{
                            "Last_Question": last_question,
                            "User_Input": new_input
                        }],
                        stream=False
                    )
                )
                
                if not completion_guard.rows:
                    print("Guardrail table failed.")
                    classification = "VALID_ANSWER" # Fallback
                else:
                    row_guard = completion_guard.rows[0]
                    classification = get_col_text(row_guard.columns.get("Classification"))
                    
                    # Log to file
                    try:
                        with open("debug_grant_manager.log", "a", encoding="utf-8") as f:
                            f.write(f"Guard Input: {new_input} | Last Q: {last_question}\n")
                            f.write(f"Guard Classification: {classification}\n")
                            f.write("-" * 20 + "\n")
                    except:
                        pass

                # Logic based on Classification
                class_upper = classification.upper()
                
                if "EXIT_INTENT" in class_upper:
                    session_state["buffer"] = ""
                    session_state["status"] = "IDLE" # Reset session status
                    return {
                        "status": "DONE",
                        "reply": "Grant search cancelled. Is there anything else I can help you with?",
                        "updated_buffer": ""
                    }
                    
                elif "GIBBERISH" in class_upper:
                    return {
                        "status": "ASKING",
                        "reply": f"I didn't understand that. {last_question}",
                        "updated_buffer": current_buffer
                    }
                    
                elif "INTERRUPTION" in class_upper:
                    # Scenario B: Interruption
                    # 1. Protect Buffer (Do not update session_state["buffer"])
                    
                    # 2. Call General Chat
                    user_id = session_state.get("user_id")
                    if not user_id:
                         chat_response = "I can't answer that right now."
                    else:
                         # Need to import chat_table_service at top, but for now use local import to avoid circular dep if any
                         from .chat_table_service import chat_table_service
                         chat_response = chat_table_service.send_message(user_id, new_input)
                    
                    # 3. Bounce Back
                    if "<<REDIRECT_TO_SEARCH>>" in chat_response:
                        # The user's interruption actually triggered a search intent!
                        # We should acknowledge it but keep them in the current flow or just suppress the token.
                        # For now, let's just suppress the token and give a generic acknowledgement.
                        chat_response = "I see you're interested in finding a grant."
                        
                    reply = f"{chat_response}\n\nNow, back to our search: {last_question}"
                    
                    return {
                        "status": "ASKING",
                        "reply": reply,
                        "updated_buffer": current_buffer
                    }
                    
                elif "VALID_ANSWER" in class_upper:
                    updated_buffer = f"{current_buffer}\nUser: {new_input}".strip()
                    session_state["buffer"] = updated_buffer
                
                else:
                    # Fallback
                    print(f"Unknown classification: {classification}")
                    updated_buffer = f"{current_buffer}\nUser: {new_input}".strip()
                    session_state["buffer"] = updated_buffer

            except Exception as e:
                print(f"Guardrail Error: {e}")
                # Fallback to appending if guard fails
                updated_buffer = f"{current_buffer}\nUser: {new_input}".strip()
                session_state["buffer"] = updated_buffer

        # 3. Call Table 1 (Detective / First Grant) - Analyze overall state
        # Only proceed if we updated the buffer (i.e., VALID_ANSWER or Fallback)
        # If we returned early (INTERRUPTION, GIBBERISH, EXIT), this won't run.
        
        try:
            # Temporary Debug: Log buffer
            try:
                with open("debug_buffer.log", "w", encoding="utf-8") as f:
                    f.write(f"--- Updated Buffer at {datetime.now()} ---\n")
                    f.write(updated_buffer)
                    f.write("\n------------------------------------------\n")
            except Exception as e:
                print(f"Buffer log error: {e}")

            completion_1 = self.client.table.add_table_rows(
                "action",
                p.RowAddRequest(
                    table_id=self.table_1_id,
                    data=[{"Basic_Company_Profile": updated_buffer}],
                    stream=False
                )
            )
            
            # DEBUG: Log full response
            try:
                with open("debug_jamai_response.log", "w", encoding="utf-8") as f:
                    f.write(f"=== JamAI Response at {datetime.now()} ===\n")
                    f.write(f"Input sent: {updated_buffer}\n")
                    f.write(f"Completion type: {type(completion_1)}\n")
                    f.write(f"Completion: {completion_1}\n")
                    if completion_1.rows:
                        row = completion_1.rows[0]
                        f.write(f"\nRow type: {type(row)}\n")
                        f.write(f"Row: {row}\n")
                        f.write(f"\nColumns: {row.columns}\n")
                        for col_name, col_val in row.columns.items():
                            f.write(f"\n  {col_name}: {col_val}\n")
                            f.write(f"    Type: {type(col_val)}\n")
            except Exception as e:
                print(f"Debug log error: {e}")
            
            if not completion_1.rows:
                return {"status": "ERROR", "reply": "No response from First Grant Agent."}
                
            row_1 = completion_1.rows[0]
            cols_1 = row_1.columns
            
            analysis = get_col_text(cols_1.get("Analysis"))
            next_question = get_col_text(cols_1.get("Follow_Up_Questions"))
            
            # Update last_question for next turn
            session_state["last_question"] = next_question

            # 4. Logic Gate (Check Analysis from Detective)
            analysis_upper = analysis.upper()
            
            # Debug Log
            print(f"DEBUG: Checking Analysis: {analysis_upper}")
            try:
                with open("debug_grant_manager.log", "a", encoding="utf-8") as f:
                    f.write(f"Checking Analysis: {analysis}\n")
            except:
                pass
            
            # Handle NO_GRANTS_FOUND case
            if "NO_GRANTS_FOUND" in analysis_upper:
                print("DEBUG: No grants found. Returning no-match message.")
                session_state["buffer"] = ""
                return {
                    "status": "DONE",
                    "reply": "Based on your business profile, we couldn't find any matching grants at this time. This could be due to specific eligibility requirements or current availability. Please check back later or contact us for personalized assistance.",
                    "updated_buffer": ""
                }
            
            if "COMPLETE" in analysis_upper or "ANALYSIS_READY" in analysis_upper or "SUFFICIENT" in analysis_upper:
                print("DEBUG: Analysis Complete. Triggering Final Grant.")
                # 5. Trigger Table 3 (Final Grant / Judge)
                judge_completion = self.client.table.add_table_rows(
                    "action",
                    p.RowAddRequest(
                        table_id=self.table_2_id,
                        data=[{"Follow_Up_Answer": updated_buffer}],
                        stream=False
                    )
                )
                
                if not judge_completion.rows:
                     return {"status": "ERROR", "reply": "No response from Judge Agent."}

                judge_row = judge_completion.rows[0]
                
                # Debug: Log Judge Columns
                try:
                    with open("debug_grant_manager.log", "a", encoding="utf-8") as f:
                        f.write(f"Judge Columns: {list(judge_row.columns.keys())}\n")
                        # Try to find the right column if Final_RAG is missing
                        val = get_col_text(judge_row.columns.get("Final_RAG"))
                        f.write(f"Extracted Verdict (Final_RAG): {val}\n")
                except:
                    pass

                verdict = get_col_text(judge_row.columns.get("Final_RAG"))
                
                # Fallback: if verdict is empty, try 'Output' or 'Response'
                if not verdict:
                    for col in ["Output", "Response", "Answer", "result"]:
                        val = get_col_text(judge_row.columns.get(col))
                        if val:
                            verdict = val
                            break
                
                session_state["buffer"] = ""
                return {
                    "status": "DONE",
                    "reply": verdict,
                    "updated_buffer": ""
                }
            else:
                print("DEBUG: Analysis Incomplete. Returning Question.")
                # Still gathering info
                return {
                    "status": "ASKING",
                    "reply": next_question,
                    "updated_buffer": updated_buffer
                }

        except Exception as e:
            print(f"Error in GrantAgent: {e}")
            return {"status": "ERROR", "reply": f"System Error: {str(e)}"}

grant_agent = GrantAgent()
