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
            
            # Check for draft content with improved formatting
            if "# Generated Blog Draft" in assistant_response and not st.session_state.get("draft_displayed", False):
                formatted_content = self._format_blog_content(assistant_response)
                st.markdown(formatted_content)
                st.session_state.draft_displayed = True
            # Check for final draft
            elif "Final approved draft:" in assistant_response:
                st.markdown("### Final Draft")
                final_content = assistant_response.split("Final approved draft:", 1)[1]
                formatted_final = self._format_blog_content(final_content)
                st.markdown(formatted_final)
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

    def _format_blog_content(self, content: str) -> str:
        """Format blog content with consistent styling and spacing."""
        # Split content into sections
        sections = content.split("\n\n")
        formatted_sections = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Format headings
            if section.startswith("#"):
                # Ensure proper heading format with spacing
                if not section.startswith("# ") and not section.startswith("## "):
                    section = f"## {section.lstrip('#').strip()}"
                formatted_sections.append(f"\n{section}\n")
            else:
                # Regular paragraph
                formatted_sections.append(section)
        
        # Join sections with proper spacing
        formatted_content = "\n\n".join(formatted_sections)
        
        # Ensure proper spacing around headings
        formatted_content = formatted_content.replace("\n###", "\n\n###")
        formatted_content = formatted_content.replace("\n##", "\n\n##")
        formatted_content = formatted_content.replace("\n#", "\n\n#")
        
        return formatted_content