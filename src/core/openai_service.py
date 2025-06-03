from typing import Dict, List, Tuple

from openai import AsyncOpenAI
from loguru import logger

from src.core.config import get_settings
from src.db.repositories.question import question_repo
from src.db.repositories.answer import answer_repo

settings = get_settings()

client = AsyncOpenAI(api_key=settings.openai_api_key)

async def check_spelling(text: str) -> Tuple[bool, str]:
    """Check for spelling errors in the text and return corrected version.
    
    Returns:
        A tuple of (has_errors, corrected_text)
    """
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set. Skipping spelling check.")
        return False, text
    
    try:
        logger.info(f"Checking spelling for: '{text[:30]}...'")
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that checks for spelling errors in questions."},
            {"role": "user", "content": f"""Check the following question for spelling errors. Return a JSON response with the corrected version and whether there were errors.

Question: "{text}"

Respond in JSON format:
{{
    "has_spelling_errors": true/false,
    "corrected_text": "the corrected question text"
}}

Important: Preserve all emojis (😊, 👍, etc.), capitalization, and punctuation in the original. Only correct actual word spelling errors. Never mark emojis as spelling errors.
"""}
        ]
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        result = response.choices[0].message.content
        logger.debug(f"OpenAI spelling check response: {result}")
        
        # Parse JSON response
        import json
        parsed = json.loads(result)
        has_errors = parsed.get("has_spelling_errors", False)
        corrected_text = parsed.get("corrected_text", text)
        
        # Only report errors if the corrected text is actually different
        if has_errors and corrected_text.strip() == text.strip():
            logger.warning(f"OpenAI reported spelling errors but returned identical text. Ignoring false positive.")
            return False, text
        
        return has_errors, corrected_text
        
    except Exception as e:
        logger.error(f"Error in OpenAI spelling check: {e}")
        return False, text

async def is_yes_no_question(text: str) -> Tuple[bool, str]:
    """Check if the text is a yes/no question using OpenAI.
    
    Returns:
        A tuple of (is_valid, reason) where reason explains any issues if not valid
    """
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set. Skipping yes/no check.")
        return True, ""  # Default to True if API key is missing
    
    # First, check if it's a non-English question - be more lenient with these
    import re
    # Check if the text contains non-Latin characters (likely non-English)
    non_latin_pattern = re.compile(r'[^\x00-\x7F]+')
    has_non_latin = bool(non_latin_pattern.search(text))
    
    # For non-English text, be extremely lenient and accept nearly everything as valid
    if has_non_latin and '?' in text:
        logger.info(f"Non-English question detected with question mark. Automatically accepting: '{text[:30]}...'")
        return True, ""
    
    try:
        logger.info(f"Checking if question is yes/no: '{text[:30]}...'")
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that evaluates if a question is suitable for yes/no or agree/disagree responses. Be extremely lenient and inclusive in your judgments - ALWAYS ERR ON THE SIDE OF ACCEPTING QUESTIONS, especially for questions about personal values, ethics, relationships, money, or self-identification."},
            {"role": "user", "content": f"""Analyze if the following question is valid for our platform. The question should be either:
1. A direct yes/no question (e.g., "Are you happy with your job?", "Do you like programming?", "Do you consider yourself a system-thinker?")
2. A statement that can be answered with degrees of agreement (e.g., "Remote work improves productivity", "Teamwork is essential")
3. A normative or value-based question that could be answered with agree/disagree (e.g., "Is it okay to use your partner's money?", "Is it normal to live at your partner's expense?")

Question: "{text}"

Important guidelines:
- Be EXTREMELY lenient - if there's ANY WAY a question could be answered with Yes/No or Agree/Disagree, the question is valid
- Questions about values, ethics, norms, or what's "okay" or "normal" are VALID
- Questions about relationships, money, or personal boundaries are VALID
- Questions in any language are VALID as long as they can be answered with Yes/No
- Questions starting with "Is it okay to..." or "Is it normal to..." are ALWAYS VALID
- Many edge cases that seem ambiguous can still be answered with Agree/Disagree

Respond in JSON format:
{{
    "is_yes_no_question": true/false,
    "reason": "Brief explanation if it's not a valid question"
}}"""}
        ]
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        result = response.choices[0].message.content
        logger.debug(f"OpenAI yes/no check response: {result}")
        
        # Parse JSON response
        import json
        parsed = json.loads(result)
        is_valid = parsed.get("is_yes_no_question", False)
        reason = parsed.get("reason", "Not a yes/no question")
        
        # Be extra lenient with obvious yes/no questions
        if not is_valid:
            # Always accept questions that contain obvious yes/no patterns
            lower_text = text.lower()
            
            # English patterns
            english_patterns = [
                "is it okay", "is it normal", "do you", "are you", "have you", 
                "would you", "could you", "should you", "is this", "are there",
                "will you", "can you", "did you", "were you", "has anyone"
            ]
            
            # Russian patterns - both formal and informal
            russian_patterns = [
                # Informal "you" forms
                "ты ", " ты ", "ты?", "любишь", "хочешь", "делаешь", 
                "следишь", "думаешь", "считаешь", "тебе", "тебя",
                # Formal "you" forms
                "вы ", " вы ", "вы?", "любите", "хотите", "делаете",
                "следите", "думаете", "считаете", "вам", "вас",
                # Question forms
                "нормально ли", "можно ли", "хорошо ли", "правильно ли", 
                "согласен ли", "по твоему мнению", "по вашему мнению",
                # Common question verbs
                "нравится", "было", "будет", "есть", "стоит"
            ]
            
            # Combine all patterns
            all_patterns = english_patterns + russian_patterns
            
            if any(pattern in lower_text for pattern in all_patterns) or "?" in text:
                logger.info(f"Overriding AI decision - accepting question with yes/no pattern: '{text[:30]}...'")
                return True, ""
        
        return is_valid, reason if not is_valid else ""
        
    except Exception as e:
        logger.error(f"Error in OpenAI yes/no check: {e}")
        return True, ""  # Default to True on error

async def check_duplicate_question(text: str, group_id: int, session) -> Tuple[bool, str, int]:
    """Check for duplicate questions within a group using OpenAI.
    
    Returns:
        A tuple of (is_duplicate, similar_question_text, similar_question_id)
    """
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set. Skipping duplicate check.")
        return False, "", 0
    
    try:
        # First, get all existing questions in the group
        existing_questions = await question_repo.get_group_questions(session, group_id)
        if not existing_questions:
            return False, "", 0
            
        # Create a list of existing question texts
        question_texts = [q.text for q in existing_questions]
        question_ids = [q.id for q in existing_questions]
        
        logger.info(f"Checking for duplicate among {len(existing_questions)} questions in group {group_id}")
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that detects duplicate questions. You should only flag questions as duplicates if they have EXACTLY the same meaning. Questions that are about similar topics but ask about different specifics or nuances should NOT be considered duplicates."},
            {"role": "user", "content": f"""Determine if the following new question is an exact duplicate of any existing questions.
            
New question: "{text}"

Existing questions:
{chr(10).join([f'{i+1}. "{q}"' for i, q in enumerate(question_texts)])}

Important: 
1. Questions may contain emojis which are valid content.
2. Do NOT mark questions as duplicates just because they are on the same topic. For example, "Do you drink alcohol?" and "Do you drink beer?" are different questions.
3. Only mark as duplicate if the questions are asking essentially the EXACT same thing, regardless of phrasing.
4. Questions with different specifics or details should be considered different questions.
5. Examples of questions that are NOT duplicates:
   - "Do you drink alcohol?" vs. "Do you drink beer?"
   - "Do you like traveling abroad?" vs. "Do you like traveling to Asia?"
   - "Are you a vegetarian?" vs. "Do you eat meat?"

Respond in JSON format:
{{
    "is_duplicate": true/false,
    "duplicate_index": null or the 1-based index of the duplicate question,
    "reason": "Brief explanation of similarity if found or why they are different"
}}"""}
        ]
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        result = response.choices[0].message.content
        logger.debug(f"OpenAI duplicate check response: {result}")
        
        # Parse JSON response
        import json
        parsed = json.loads(result)
        is_duplicate = parsed.get("is_duplicate", False)
        duplicate_index = parsed.get("duplicate_index")
        reason = parsed.get("reason", "")
        
        if is_duplicate and duplicate_index is not None and 1 <= duplicate_index <= len(question_texts):
            # Convert 1-based index from GPT to 0-based index
            idx = duplicate_index - 1
            return True, question_texts[idx], question_ids[idx]
            
        return False, "", 0
        
    except Exception as e:
        logger.error(f"Error in OpenAI duplicate check: {e}")
        return False, "", 0

async def get_text_embedding(text: str) -> List[float]:
    """Generate text embedding using OpenAI."""
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set. Returning empty embedding.")
        return []
        
    logger.info("Generating text embedding (placeholder)...")
    # TODO: Implement actual OpenAI embedding generation
    # response = await client.embeddings.create(input=text, model="text-embedding-ada-002")
    # return response.data[0].embedding
    return [0.0] * 1536 # Placeholder dimension 

async def ai_match_analysis(
    session,
    user1_id: int,
    user2_id: int,
    group_id: int,
    user_locale: str = "ru",
    cache=None
) -> str:
    """
    Анализирует ответы двух пользователей и выдает summary: что объединяет, где могут дополнить друг друга, общие категории, различия.
    Использует тексты вопросов и новую структуру промпта.
    """
    import json
    from src.db.repositories.question import question_repo
    from src.db.repositories.answer import answer_repo
    from src.db.models import Answer, Question

    # Получаем ответы обоих пользователей
    answers1 = await answer_repo.get_user_answers_for_group(session, user1_id, group_id)
    answers2 = await answer_repo.get_user_answers_for_group(session, user2_id, group_id)
    # Получаем все вопросы по id
    qids = list(set([a.question_id for a in answers1] + [a.question_id for a in answers2]))
    questions = await question_repo.get_questions_by_ids(session, qids)
    qmap = {q.id: q for q in questions}

    # Сопоставляем ответы по question_id
    a1_map = {a.question_id: a for a in answers1}
    a2_map = {a.question_id: a for a in answers2}

    shared_questions = []
    complementary_questions = []
    uniqueA = []
    uniqueB = []

    for qid in qids:
        a1 = a1_map.get(qid)
        a2 = a2_map.get(qid)
        if not a1 or not a2:
            if a1 and not a2:
                uniqueA.append(qmap[qid].text)
            elif a2 and not a1:
                uniqueB.append(qmap[qid].text)
            continue
        # Совпадение: значения равны или отличаются не более чем на 1
        if abs(a1.value - a2.value) <= 1:
            shared_questions.append(qmap[qid].text)
        # Дополнение: значения противоположны (например, -2 и 2, -1 и 1)
        elif (a1.value * a2.value < 0) and (abs(a1.value) == abs(a2.value)):
            complementary_questions.append(qmap[qid].text)
        # Сильное различие (но не строго противоположные): можно добавить в uniqueA/uniqueB
        else:
            if abs(a1.value) > abs(a2.value):
                uniqueA.append(qmap[qid].text)
            else:
                uniqueB.append(qmap[qid].text)

    # Формируем промпт
    prompt = f"""
🎯 Цель:
Проанализируй ответы двух пользователей на набор из 15–50 вопросов, каждый из которых оценивается по шкале от -2 до 2. Помоги им начать общение, основываясь на совпадениях и различиях. Избегай банальных фраз, пиши по делу, дружелюбно и спокойно.

📝 Инструкция:

Напиши вступление в дружеском тоне — как будто ты их знакомый, который хочет помочь начать разговор. Подчеркни, что всё важное выясняется только при личном общении, но ты попробуешь предположить, что может сблизить и в чём они могут дополнять друг друга. Не используй фальшивую мотивацию, пафос или обещания "глубокой связи".

Выдели общие ценности — темы, на которые оба пользователя дали высокие (2 или 1) или низкие (-2 или -1) совпадающие ответы.

Выдели взаимодополняющие различия — где у одного сильное мнение, а у другого противоположное. Объясни, как это может дать интересную динамику.

Предложи 2–3 вопроса, которые они могли бы обсудить между собой. Вопросы должны быть по-настоящему осмысленными, чтобы помочь начать разговор, без искусственности.

📌 Принципы:

Используй эмодзи умеренно, чтобы текст выглядел живо, но не кринжово.

Пиши так, будто ты хороший друг.

Избегай оценочных суждений о самих людях — только об их ответах.

Не упоминай баллы или числа напрямую.

Не используй клише вроде "идеальный матч", "глубокая связь", "созданы друг для друга" и пр.

Говори в форме предположений, а не утверждений: "возможно", "похоже", "я бы сказал", "может быть".
"""
    messages = [
        {"role": "system", "content": "You are a thoughtful matching assistant that helps people connect meaningfully based on their answers to deep, value-based questions."},
        {"role": "user", "content": prompt}
    ]
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.5,
        max_tokens=400
    )
    result = response.choices[0].message.content.strip()
    return result

# Remove the categorize_question function 