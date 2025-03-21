import streamlit as st

class DisplayResultStreamlit:
    def display_result(self, response: dict, usecase: str) -> str:
        if usecase == "Blog Generation":
            # Always prioritize direct sections display
            if "sections" in response:
                sections = response.get("sections", [])
                if sections and not st.session_state.get("outline_displayed", False):
                    outline_text = "### Generated Outline\n\n"
                    for section in sections:
                        outline_text += f"**{section['name']}**: {section['description']}\n\n"
                    st.markdown(outline_text)
                    st.markdown("Please review the outline above.")
                    st.session_state.outline_displayed = True
                    return outline_text

            # Process message-based content
            messages = response.get("messages", [])
            if not messages:
                return "No response generated."
            
            assistant_response = messages[-1].content if messages else "No response generated."
            
            # Check for draft content
            if "# Generated Blog Draft" in assistant_response and not st.session_state.get("draft_displayed", False):
                st.markdown(assistant_response)
                st.session_state.draft_displayed = True
            # Check for final draft
            elif "Final approved draft:" in assistant_response:
                st.markdown("### Final Draft")
                st.markdown(assistant_response.split("Final approved draft:", 1)[1])
            # Display other messages without repetition
            elif not any(x in assistant_response for x in ["Generated outline:", "# Generated Blog Draft", "Final approved draft:"]):
                st.markdown(assistant_response)
            
            return assistant_response

        elif usecase == "Basic Chatbot":
            assistant_response = response.get("messages", [{}])[-1].content if response.get("messages") else "No response generated."
            st.markdown(assistant_response)
            return assistant_response

        elif usecase == "Chatbot with Tool":
            if "messages" in response:
                assistant_response = response.get("messages", [{}])[-1].content
                tool_output = response.get("tool_output", "")
                if tool_output:
                    st.markdown("**Tool Output:**")
                    st.code(tool_output, language="text")
                st.markdown(assistant_response)
                return assistant_response
            return "No response generated."

        elif usecase == "Coding Peer Review":
            review_output = response.get("review_output", "No review generated.")
            corrected_code = response.get("corrected_code", "")
            st.markdown("### Code Review Feedback")
            st.markdown(review_output)
            if corrected_code:
                st.markdown("### Corrected Code")
                st.code(corrected_code, language="python")
            return review_output

        else:
            st.error(f"Unknown use case: {usecase}")
            return ""