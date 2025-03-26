import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

class DisplayResultStreamlit:
    def __init__(self, graph, with_message_history, config, usecase):
        self.graph = graph
        self.with_message_history = with_message_history
        self.config = config
        self.usecase = usecase
        self.session_history = self._get_session_history()

    def _get_session_history(self):
        from langchain_community.chat_message_histories import ChatMessageHistory
        store = {}
        session_id = self.config["configurable"]["session_id"]
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        return store[session_id]

    def display_chat_history(self):
        """Display the chat history from the session."""
        for message in self.session_history.messages:
            role = "user" if isinstance(message, HumanMessage) else "assistant"
            with st.chat_message(role):
                st.markdown(message.content, unsafe_allow_html=True)

    def process_user_input(self):
        """Process user input and display results based on the use case."""
        if self.usecase == "Blog Generation":
            self._handle_blog_generation()
        else:
            self._handle_chatbot_input()

    def _handle_blog_generation(self):
        if st.session_state.waiting_for_feedback:
            self._process_feedback()
        elif not st.session_state.blog_requirements_collected:
            self._collect_blog_requirements()
        else:
            self._process_graph_stream()

    def _collect_blog_requirements(self):
        st.markdown("### Blog Requirements")
        with st.form("blog_requirements_form"):
            topic = st.text_input("Topic", placeholder="e.g., The Future of AI in Healthcare")
            objective = st.radio("Objective", ["Informative", "Persuasive", "Storytelling", "Other"])
            if objective == "Other":
                objective = st.text_input("Specify Objective", placeholder="Enter custom objective")
            target_audience = st.radio("Target Audience", ["Beginners", "Experts", "General Audience", "Other"])
            if target_audience == "Other":
                target_audience = st.text_input("Specify Target Audience", placeholder="Enter custom audience")
            tone_style = st.radio("Tone & Style", ["Formal", "Casual", "Technical", "Engaging", "Other"])
            if tone_style == "Other":
                tone_style = st.text_input("Specify Tone & Style", placeholder="Enter custom tone and style")
            word_count = st.number_input("Word Count", min_value=100, max_value=5000, value=1000, step=100)
            structure = st.text_area("Structure", placeholder="e.g., Introduction, Key Points, Conclusion")
            submit_button = st.form_submit_button("Submit Blog Requirements")

            if submit_button:
                if not all([topic, objective, target_audience, tone_style, structure]):
                    st.error("Please fill in all required fields.")
                    return
                user_message = f"Topic: {topic} Objective: {objective} Target Audience: {target_audience} Tone & Style: {tone_style} Word Count: {word_count} Structure: {structure}"
                self.session_history.add_user_message(user_message)
                with st.chat_message("user"):
                    st.markdown(user_message)
                st.session_state.blog_requirements_collected = True
                self._process_graph_stream(HumanMessage(content=user_message))

    def _process_feedback(self):
        latest_state = st.session_state.graph_state.values if st.session_state.graph_state else {}
        if "completed_sections" in latest_state and not st.session_state.get("draft_displayed", False):
            with st.chat_message("assistant"):
                draft_content = "\n\n".join(latest_state["completed_sections"])
                st.markdown("### Generated Draft")
                st.markdown(draft_content)
                st.session_state.draft_displayed = True

        current_node = st.session_state.graph_state.next[0] if st.session_state.graph_state.next else None
        if current_node == "outline_review":
            st.write("Review the outline:")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Looks good", key="outline_approve"):
                    st.session_state.outline_feedback = "approved"
                    st.session_state.waiting_for_feedback = False
            with col2:
                if st.button("Add more details", key="outline_reject"):
                    st.session_state.outline_feedback = "add_more_details"
                    st.session_state.waiting_for_feedback = False
        elif current_node == "draft_review":
            st.write("Review the draft:")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Looks good", key="draft_approve"):
                    st.session_state.draft_feedback = "approved"
                    st.session_state.waiting_for_feedback = False
                    st.session_state.draft_displayed = False
            with col2:
                if st.button("Add more details", key="draft_reject"):
                    st.session_state.draft_feedback = "add_more_details"
                    st.session_state.waiting_for_feedback = False
                    st.session_state.draft_displayed = False

        if not st.session_state.waiting_for_feedback:
            self._process_graph_stream()

    def _handle_chatbot_input(self):
        user_message = st.chat_input("Enter your message:")
        if user_message:
            self.session_history.add_user_message(user_message)
            with st.chat_message("user"):
                st.markdown(user_message, unsafe_allow_html=True)
            self._process_graph_stream(HumanMessage(content=user_message))

    def _process_graph_stream(self, input_message=None):
        with st.spinner("Processing..."):
            input_data = {"messages": [input_message]} if input_message else None
            for event in (self.graph.stream(input_data, self.config) if input_data else self.graph.stream(None, self.config)):
                for node, state in event.items():
                    if "messages" in state and state["messages"]:
                        with st.chat_message("assistant"):
                            self._display_result(state)
                        self.session_history.add_ai_message(state["messages"][-1].content)
                graph_state = self.graph.get_state(self.config)
                if graph_state.next and graph_state.next[0] in ["outline_review", "draft_review"]:
                    st.session_state.waiting_for_feedback = True
                    st.session_state.graph_state = graph_state
                    break
                elif not graph_state.next and self.usecase == "Blog Generation":
                    st.session_state.blog_requirements_collected = False
                    with st.chat_message("assistant"):
                        st.markdown("✅ Blog generation completed!")
                    if st.button("New Blog Generation"):
                        self.session_history.clear()
                        st.session_state.graph_state = None
                        st.session_state.waiting_for_feedback = False
                        st.rerun()

    def _display_result(self, response):
        if self.usecase == "Blog Generation":
            if "sections" in response and not st.session_state.get("outline_displayed", False):
                outline_text = "### Generated Outline\n\n" + "\n\n".join(f"**{s['name']}**: {s['description']}" for s in response["sections"])
                st.markdown(outline_text)
                st.markdown("Please review the outline above.")
                st.session_state.outline_displayed = True
            messages = response.get("messages", [])
            if messages:
                content = messages[-1].content
                if "# Generated Blog Draft" in content and not st.session_state.get("draft_displayed", False):
                    st.markdown(self._format_blog_content(content))
                    st.session_state.draft_displayed = True
                elif "Final approved draft:" in content:
                    st.markdown("### Final Draft")
                    st.markdown(self._format_blog_content(content.split("Final approved draft:", 1)[1]))
                elif not any(x in content for x in ["Generated outline:", "# Generated Blog Draft", "Final approved draft:"]):
                    st.markdown(content)

        elif self.usecase == "Basic Chatbot":
            st.markdown(response.get("messages", [{}])[-1].content)

        elif self.usecase == "Chatbot with Tool":
            content = response.get("messages", [{}])[-1].content
            tool_output = response.get("tool_output", "")
            if tool_output:
                st.markdown("**Tool Output:**")
                st.code(tool_output, language="text")
            st.markdown(content)

        elif self.usecase == "Coding Peer Review":
            st.markdown("### Code Review Feedback")
            st.markdown(response.get("review_output", "No review generated."))
            if corrected_code := response.get("corrected_code", ""):
                st.markdown("### Corrected Code")
                st.code(corrected_code, language="python")

    def _format_blog_content(self, content):
        sections = content.strip().split("\n\n")
        formatted = "\n\n".join(
            f"\n\n{s.strip()}" if s.startswith("#") else s.strip()
            for s in sections if s.strip()
        )
        return formatted.replace("\n###", "\n\n###").replace("\n##", "\n\n##").replace("\n#", "\n\n#")