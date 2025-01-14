
initialModel = 'mistralai/Mistral-7B-Instruct-v0.3'
secondaryModel = 'CohereForAI/c4ai-command-r-plus'
tertiaryModel = 'google/gemma-1.1-7b-it'
ancillaryModel = 'meta-llama/Meta-Llama-3.1-8B-Instruct'
adjacentModel = "meta-llama/Meta-Llama-3.1-70B-Instruct"

#Open Question
def open_question_chat_setup(payload,queryNumber, modelId):
    if modelId == initialModel or modelId == ancillaryModel or modelId == adjacentModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": open_question_question_base},
                {"role": "assistant", "content": "What are the Source Materials?"},
                {"role": "user", "content": str(payload)},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": open_question_answer_base},
                {"role": "assistant", "content": "What's your question?"},
                {"role": "user", "content": str(payload)},
                ]
            
    if modelId == secondaryModel or modelId == tertiaryModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": open_question_question_base +  'Source Materials:  \\' + str(payload)}
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": open_question_answer_base + str(payload)},
                ]
    
    return chat
    
    
#Question Answer
def question_answer_chat_setup(payload,queryNumber, modelId):
    if modelId == initialModel or modelId == ancillaryModel or modelId == adjacentModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": question_answer_question_base},
                {"role": "assistant", "content": "What is the conversation?"},
                {"role": "user", "content": f'Conversation: Question:  {payload["generate_question"]}  Answer:  {payload["generate_answer"]}'}
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": question_answer_answer_base},
                {"role": "assistant", "content": "What is the conversation?"},
                {"role": "user", "content": f'Conversation: Question:  {payload["generate_question"]}  Answer:  {payload["generate_answer"]}\
                Follow-up Question: {payload["generate_question_1"]}'},
                ]
    if modelId == secondaryModel or modelId == tertiaryModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": f'{question_answer_question_base} Conversation: Question:  {payload["generate_question"]}  Answer:  {payload["generate_answer"]}'},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": f'{question_answer_answer_base} Conversation: Question:  {payload["generate_question"]}  \
                Answer:  {payload["generate_answer"]} Follow-up Question: {payload["generate_question_1"]}'},
                ]
    return chat

# BrainStorm
def brainstorm_chat_setup(payload,queryNumber, modelId):
    if modelId == initialModel or modelId == ancillaryModel or modelId == adjacentModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": brainstorm_question_base},
                {"role": "assistant", "content": "What's the source material?"},
                {"role": "user", "content": str(payload)},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": brainstorm_answer_base},
                {"role": "assistant", "content": "What's your question?"},
                {"role": "user", "content": str(payload)},
                ]
    if modelId == secondaryModel or modelId == tertiaryModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": brainstorm_question_base + str(payload)},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": brainstorm_answer_base + str(payload)},
                ]
    
    return chat

# Creative Writing
def creative_chat_setup(payload,queryNumber, modelId):
    if modelId == initialModel or modelId == ancillaryModel or modelId == adjacentModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": "You analyze source materials for creative writers."},
                {"role": "assistant", "content": "What would you like me to do?"},
                {"role": "user", "content": f'Choose an idea that would be interesting to generate text from.  \
                Return it in one sentence formed as a question.  The writer will not have access to your source materials. \
                Feel free to mention that it is for a creative writing prompt. \
                Choose your idea for a creative writing prompt from here : {payload}'},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": "You are an expert creative writer that uses unique approaches to different ideas."},
                {"role": "assistant", "content": "What would you like me to write about?"},
                {"role": "user", "content": payload},
                ]
            
    if modelId == secondaryModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": f'You analyze source materials for creative writers. \
                Choose an idea that would be interesting to generate text from. \
                Return it in one sentence formed as a question. The writer will not have access to your source materials. \
                You are free to mention it is for a creative writing prompt. \
                Choose your idea for a creative writing prompt from here : {payload}'},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": f'You are an expert creative writer that uses unique approaches to different ideas. {payload}'},
                ]
    if modelId == tertiaryModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": f'You analyze source materials for creative writers. \
                Choose an idea that would be interesting to generate text from. \
                Return it in one sentence formed as a question. The writer will not have access to your source materials. \
                Make sure to mention that it\'s for a creative writing topic. \
                Choose your idea for a creative writing prompt from here.: {payload}'}]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": f'{payload}'},
                ]
    
    return chat


# Poem
def poem_chat_setup(payload,queryNumber, modelId):
    if modelId == initialModel or modelId == ancillaryModel or modelId == adjacentModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": poem_question_base},
                {"role": "assistant", "content": "What are the source materials?"},
                {"role": "user", "content": 'Now, based on the following source materials, generate a theme for a poem:' + str(payload)},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": poem_answer_base},
                {"role": "assistant", "content": "What are the poem and theme?"},
                {"role": "user", "content": ' Now, based on the following poem and theme, create a new poem: ' + str(payload)}
                ]
            
    if modelId == secondaryModel or modelId == tertiaryModel:
        if queryNumber == 1:
            chat = [
                {"role": "user", "content": poem_question_base + ' Now, based on the following source materials, generate a theme for a poem: ' + str(payload)},
                ]
        if queryNumber == 2:
            chat = [
                {"role": "user", "content": poem_answer_base + ' Now, based on the following poem and theme, create a new poem: ' + str(payload)},
                ]
    
    
    return chat
    
brainstorm_question_base = 'You are an AI assistant specialized in analyzing information and   \
formulating thought-provoking questions for brainstorming sessions. Your task is to examine the given   \
source materials and generate an insightful, open-ended question that will stimulate creative thinking and problem-solving.  \
Instructions:  \
1. Carefully review the provided source materials.  \
2. Identify key themes, challenges, or opportunities present in the materials.  \
3. Formulate a brainstorming question that:  \
   - Addresses a significant aspect or combines multiple aspects from the source materials  \
   - Is open-ended and encourages diverse thinking  \
   - Has the potential to generate innovative solutions or ideas  \
   - Is clear, concise, and engaging  \
   - Challenges conventional thinking or approaches  \
5. Format your response as follows:  \
   Brainstorming Question: [Your question here]  \
Remember to:  \
- Ensure the question is not too narrow or specific, allowing for a wide range of possible answers  \
- Avoid questions that can be answered with a simple yes or no  \
- Frame the question in a way that encourages positive, solution-oriented thinking  \
- Consider the potential for cross-disciplinary approaches in your question formulation  \
Now, based on the following source materials, generate a brainstorming question: '

    
brainstorm_answer_base = 'You are a creative and analytical AI assistant tasked with conducting a comprehensive brainstorming session. \
Your goal is to generate diverse, innovative, and practical ideas in response to the given question or problem. Instructions:  \
1. Analyze the question or problem presented.  \
2. Generate at least 10 unique ideas or solutions, ranging from conventional to highly creative.  \
3. For each idea, provide:  \
   - A brief description (1-2 sentences)  \
   - At least one potential benefit  \
   - At least one potential challenge or limitation  \
4. After listing the ideas, provide a summary that includes:  \
   - Common themes or patterns among the ideas  \
   - The most promising ideas and why  \
   - Potential next steps or areas for further exploration  \
Remember to:  \
- Think outside the box and consider unconventional approaches  \
- Draw from various disciplines and industries for inspiration  \
- Consider both short-term and long-term implications  \
- Be specific and actionable in your suggestions  \
- Maintain a positive and solution-oriented mindset  \
Now, based on the following question or problem, begin your brainstorming session: '

open_question_question_base = 'You are an expert in synthesizing information and creating engaging questions.   \
Your task is to analyze the following source materials, which may not be directly connected or correlated, and   \
generate one thought-provoking question that integrates elements from these sources. Keep in mind that the person  \
answering this question will not have access to the original source materials.  \
Instructions:   \
1. Be self-contained and understandable without reference to the source materials  \
2. Encourage critical thinking and exploration of broader concepts  \
3. Be open-ended, avoiding simple yes/no answers  \
4. Highlight an intriguing connection, contrast, or theme derived from the materials  \
5. Be relevant to general knowledge or current affairs  \
6. Spark curiosity and stimulate discussion  \
Remember to: \
- carefully review the provided source materials  \
- craft a single question that meets the criteria.  \
- the question should be clear, concise, and designed to be answered without specific knowledge of the source materials.  \
Format your response as follows:  \
Generated Question:  \
[Your thought-provoking question here]'

open_question_answer_base = 'You are an expert in providing comprehensive and insightful answers to open-ended questions. \
Your task is to analyze the given question and provide a well-structured, informative response.  \
Instructions:  \
1. Directly address the main points of the question  \
2. Provide a balanced and objective perspective   \
3. Include relevant examples, facts, or data where appropriate  \
4. Consider multiple angles or viewpoints on the topic  \
5. Be clear, concise, and engaging for the reader  \
Please format your response as follows:  \
Answer  \
[Provide your main answer here, addressing the key aspects of the question. This should be a concise summary of your thoughts, typically 2-3 sentences.]  \
Key Points  \
[List 3-5 key points that expand on your main answer]  \
Detailed Explanation  \
[Offer a more in-depth explanation of your answer, elaborating on the key points. This section should be 2-3 paragraphs long.]  \
Examples or Evidence  \
[Provide specific examples, case studies, or evidence that support your answer. If applicable, include data or statistics.]  \
Conclusion  \
[Summarize your main points and provide a final thought or insight on the question.]  \
Now, please provide your response to the following open-ended question:'

poem_question_base = 'You are an AI assistant specialized in analyzing information and generating themes for creative writing. \
Your task is to examine the given source materials and extract a central theme that can be used to create a poem. \
\
Instructions: \
1. Carefully review the provided source materials. \
2. Identify key themes, emotions, or messages present in the materials. \
3. Formulate a single-sentence theme that: \
    - Captures the essence or combines multiple aspects from the source materials \
    - Is clear, concise, and evocative \
    - Provides a strong foundation for poetic inspiration \
4. Turn the theme into a prompt and explicitly ask for a poem written about it\
5. Return only prompt\
\
Format your response as follows: \
Poem Prompt: [Your prompt here] \
\
Remember to: \
\
- Ensure the theme is not too narrow or specific, allowing for creative interpretation \
- Avoid themes that are overly complex or abstract \
- Frame the theme in a way that evokes imagery and emotion \
- Consider the potential for various poetic forms and styles in your theme formulation \
- Turn the theme into a prompt and explicitly ask for a poem written about it\
- Return only the prompt'

poem_answer_base = 'You are a creative and analytical AI assistant tasked with analyzing a poem\'s style \
and creating a new poem based on a given theme.\
\
Instructions:\
\
1. Review the provided poem and carefully analyze its style, including aspects such as tone, structure, rhythm, imagery, and language.\
2. Identify key stylistic elements that define the poem\'s unique character.\
3. Based on the given theme, write a new poem that:\
    - Incorporates the identified stylistic elements\
    - Reflects the essence and mood of the original poem\
    - Explores the given theme in a creative and evocative manner\
4. Return only the poem\
\
Format your response as follows:\
\
New Poem: [Your poem here]\
\
Remember to:\
\
- Stay true to the original poem\'s style while creating fresh and original content\
- Ensure the new poem aligns with the given theme\
- Use language and imagery that evoke emotion and imagination\
- Consider the potential for various poetic forms and structures in your new poem.\
- Return only the poem'

question_answer_question_base = 'You are an AI assistant specialized in generating follow-up questions for conversations. \
Your task is to examine a given question and answer chat conversation and generate an additional follow-up question\
to continue the discussion.\
\
Instructions:\
\
1. Review the provided question and answer conversation.\
2. Identify the key topics, themes, or details discussed.\
3. Formulate a follow-up question that is relevant, engaging, and encourages further discussion.\
4. Return only the follow-up question\
Format your response as follows:\
Follow-Up Question: [Your follow-up question here]\
\
Remember:\
\
- The follow-up question should be contextually relevant to the conversation.\
- Aim to deepen the discussion or explore related aspects of the topic.\
- Ensure the question is open-ended to invite a detailed response.\
- Return only the follow-up question.'

question_answer_answer_base = 'You are an AI assistant specialized in generating answers for ongoing conversations. \
Your task is to examine a given chat conversation consisting of a question, answer and an additional follow-up question,  \
then generate an appropriate answer.\
\
Instructions:\
\
1. Review the provided question and follow-up question conversation.\
2. Understand the context and details discussed in the conversation.\
3. Formulate a relevant and informative answer to the follow-up question.\
4. Return only the answer\
Format your response as follows:\
Generated Answer: [Your answer here]\
\
Remember:\
\
- The answer should be contextually relevant to the conversation.\
- Provide a detailed and informative response.\
- Ensure the answer is clear, concise, and encourages further engagement if necessary.\
- Return only the answer.'

