"""L3/L4 worksheet activity taxonomy.

This file is intentionally declarative. The worksheet builder uses these
activity codes to keep page goals explicit, avoid vague task labels, and record
which activity type was selected for QA or later TG-only generation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TextType = Literal["any", "fiction", "non-fiction"]
AnswerType = Literal["closed", "open"]


@dataclass(frozen=True)
class WorksheetActivity:
    code: str
    page: int
    module: str
    goal: str
    student_instruction: str
    l3_support: str
    l4_support: str
    required_fields: tuple[str, ...] = ()
    min_items: int = 4
    min_level: int = 3
    max_level: int = 4
    text_type: TextType = "any"
    priority: int = 50
    answer_type: AnswerType = "closed"
    input_source: tuple[str, ...] = ()
    required_assets: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()
    answer_key_format: str = ""
    release_blockers: tuple[str, ...] = ()
    requires_unique_answer: bool = True
    optional: bool = False


L34_WORKSHEET_ACTIVITIES: dict[str, WorksheetActivity] = {
    # Page 1: Vocabulary understanding.
    "vocab_word_definition_matching": WorksheetActivity(
        code="vocab_word_definition_matching",
        page=1,
        module="Vocabulary",
        goal="Match core words with clear meanings.",
        student_instruction="Match each word with its meaning.",
        l3_support="Short meanings; picture support when possible.",
        l4_support="Clear English meanings; more precise distractors.",
        required_fields=("word", "definition", "answer_map"),
        min_items=4,
        priority=30,
    ),
    "vocab_word_picture_matching": WorksheetActivity(
        code="vocab_word_picture_matching",
        page=1,
        module="Vocabulary",
        goal="Match core words with pictures.",
        student_instruction="Match each word with the picture.",
        l3_support="Use pictures for each core word.",
        l4_support="Use pictures only when the word is visually clear.",
        required_fields=("word", "image"),
        min_items=4,
        priority=10,
        required_assets=("image",),
    ),
    "vocab_choose_picture": WorksheetActivity(
        code="vocab_choose_picture",
        page=1,
        module="Vocabulary",
        goal="Choose the picture that shows each core word.",
        student_instruction="Choose the picture.",
        l3_support="Use clean visual clues and two or three options.",
        l4_support="Use pictures only for visual core words.",
        required_fields=("word", "options", "answer"),
        min_items=4,
        priority=20,
        required_assets=("image",),
    ),
    "vocab_choose_meaning": WorksheetActivity(
        code="vocab_choose_meaning",
        page=1,
        module="Vocabulary",
        goal="Choose the meaning of each core word.",
        student_instruction="Choose the meaning.",
        l3_support="Two choices with short, concrete meanings.",
        l4_support="Two or three choices with clear contrasts.",
        required_fields=("word", "options", "answer"),
        min_items=4,
        priority=40,
    ),

    # Page 2: Vocabulary application.
    "vocab_contextual_word_bank_cloze": WorksheetActivity(
        code="vocab_contextual_word_bank_cloze",
        page=2,
        module="Vocabulary",
        goal="Use core words in short story-based sentences.",
        student_instruction="Use the words to fill each blank.",
        l3_support="Full word bank; each word used once when possible.",
        l4_support="Context clues can be longer; word bank may include stronger distractors.",
        required_fields=("sentence", "word_bank", "answer"),
        min_items=3,
        priority=10,
    ),
    "vocab_contextual_choice": WorksheetActivity(
        code="vocab_contextual_choice",
        page=2,
        module="Vocabulary",
        goal="Choose the core word that fits a context clue.",
        student_instruction="Read each clue and circle the correct word.",
        l3_support="Two or three choices; concrete clues.",
        l4_support="Three choices; clues may use function or context.",
        required_fields=("clue", "options", "answer"),
        min_items=3,
        priority=20,
    ),
    "vocab_contextual_clue_write": WorksheetActivity(
        code="vocab_contextual_clue_write",
        page=2,
        module="Vocabulary",
        goal="Write the core word from a context or meaning clue.",
        student_instruction="Read the clue and write the word.",
        l3_support="Word bank or first-letter support preferred.",
        l4_support="May omit the full word bank when clues are clear.",
        required_fields=("clue", "answer"),
        min_items=3,
        priority=30,
    ),
    "vocab_multi_word_cloze": WorksheetActivity(
        code="vocab_multi_word_cloze",
        page=2,
        module="Vocabulary",
        goal="Use a complete core phrase in context.",
        student_instruction="Use the phrases to fill each blank.",
        l3_support="Keep phrases intact; provide full phrase bank.",
        l4_support="Use story context to choose complete phrases.",
        required_fields=("phrase", "sentence", "answer"),
        min_items=3,
        priority=15,
    ),
    "vocab_category_sorting": WorksheetActivity(
        code="vocab_category_sorting",
        page=2,
        module="Vocabulary",
        goal="Sort core words by meaning or use.",
        student_instruction="Sort the words.",
        l3_support="Two simple categories.",
        l4_support="More precise categories when the word set supports it.",
        required_fields=("categories", "words", "answer_map"),
        min_items=4,
        priority=60,
        optional=True,
    ),

    # Page 3: Sentence recognition.
    "sentence_target_pattern_choice": WorksheetActivity(
        code="sentence_target_pattern_choice",
        page=3,
        module="Sentence",
        goal="Recognize the syllabus sentence frame in correct sentences.",
        student_instruction="Choose the sentence with the target pattern.",
        l3_support="Two choices; one clear error point.",
        l4_support="Two or three choices; still one main error point.",
        required_fields=("sentence_frame", "options", "answer"),
        min_items=3,
        priority=10,
    ),
    "sentence_correct_sentence_choice": WorksheetActivity(
        code="sentence_correct_sentence_choice",
        page=3,
        module="Sentence",
        goal="Choose the grammatically correct sentence.",
        student_instruction="Choose the correct sentence.",
        l3_support="Two choices; visible support when useful.",
        l4_support="Three choices when the contrast is clear.",
        required_fields=("options", "answer"),
        min_items=3,
        priority=20,
    ),

    # Page 4: Sentence practice.
    "sentence_grammar_word_cloze": WorksheetActivity(
        code="sentence_grammar_word_cloze",
        page=4,
        module="Sentence",
        goal="Complete the target sentence using the correct grammar word or phrase.",
        student_instruction="Choose the correct words to complete each sentence.",
        l3_support="Full sentence frame and clear word bank.",
        l4_support="Less support; more grammar-focused distractors.",
        required_fields=("sentence_frame", "options", "answer"),
        min_items=3,
        priority=20,
    ),
    "sentence_complete_frame": WorksheetActivity(
        code="sentence_complete_frame",
        page=4,
        module="Sentence",
        goal="Complete the syllabus sentence frame.",
        student_instruction="Complete the sentence frame.",
        l3_support="Fill one or two blanks only.",
        l4_support="May complete a longer phrase if the frame supports it.",
        required_fields=("sentence_frame", "answer"),
        min_items=3,
        priority=15,
    ),
    "sentence_guided_writing": WorksheetActivity(
        code="sentence_guided_writing",
        page=4,
        module="Sentence",
        goal="Write single sentences with strong sentence-frame support.",
        student_instruction="Write one sentence for each prompt.",
        l3_support="Full frame, keyword, and long writing line.",
        l4_support="Frame or starter; still single-sentence practice.",
        required_fields=("sentence_frame", "prompt"),
        min_items=3,
        priority=30,
        requires_unique_answer=False,
    ),
    "sentence_grammar_correction": WorksheetActivity(
        code="sentence_grammar_correction",
        page=4,
        module="Sentence",
        goal="Correct one sentence-level grammar or pattern error.",
        student_instruction="Correct each sentence.",
        l3_support="Use only obvious single errors.",
        l4_support="May use one or two related errors.",
        required_fields=("wrong_sentence", "correct_sentence"),
        min_items=3,
        min_level=4,
        priority=40,
    ),
    "sentence_reorder_words": WorksheetActivity(
        code="sentence_reorder_words",
        page=4,
        module="Sentence",
        goal="Put words in order to make the target sentence.",
        student_instruction="Put the words in order.",
        l3_support="Short sentences and full punctuation.",
        l4_support="Longer target-pattern sentences.",
        required_fields=("scrambled_words", "answer"),
        min_items=3,
        priority=50,
        optional=True,
    ),

    # Page 5: Reading direct facts.
    "reading_true_false_literal": WorksheetActivity(
        code="reading_true_false_literal",
        page=5,
        module="Reading",
        goal="Check directly stated facts.",
        student_instruction="Read the passage. Write T (true) or F (false).",
        l3_support="False items change one clear detail.",
        l4_support="May include slightly longer factual statements.",
        required_fields=("statement", "answer"),
        min_items=4,
        priority=10,
    ),
    "reading_supported_sentence_choice": WorksheetActivity(
        code="reading_supported_sentence_choice",
        page=5,
        module="Reading",
        goal="Choose the sentence supported by the text.",
        student_instruction="Read the passage. Circle the correct sentence.",
        l3_support="Two or three choices; direct text support.",
        l4_support="Three choices with precise detail changes.",
        required_fields=("options", "answer", "evidence"),
        min_items=4,
        priority=20,
    ),
    "reading_literal_mc": WorksheetActivity(
        code="reading_literal_mc",
        page=5,
        module="Reading",
        goal="Answer Who, What, Where, or When questions from the text.",
        student_instruction="Choose the correct answer.",
        l3_support="Mostly direct details.",
        l4_support="Can include more exact wording from the passage.",
        required_fields=("question", "options", "answer", "evidence"),
        min_items=4,
        priority=30,
        optional=True,
    ),

    # Page 6: Reading integration.
    "reading_summary_cloze": WorksheetActivity(
        code="reading_summary_cloze",
        page=6,
        module="Reading",
        goal="Complete a text-based summary or fact sentence.",
        student_instruction="Complete the text summary.",
        l3_support="Word bank and short blanks.",
        l4_support="Fewer hints; blanks may require phrases.",
        required_fields=("summary_sentence", "answer"),
        min_items=4,
        text_type="any",
        priority=40,
    ),
    "reading_sequence_ordering": WorksheetActivity(
        code="reading_sequence_ordering",
        page=6,
        module="Reading",
        goal="Put story events or process steps in order.",
        student_instruction="Number the events in order.",
        l3_support="Four to five short events.",
        l4_support="Five events or process steps when supported by text.",
        required_fields=("events", "answer_order"),
        min_items=4,
        text_type="fiction",
        priority=10,
    ),
    "reading_text_based_correction": WorksheetActivity(
        code="reading_text_based_correction",
        page=6,
        module="Reading",
        goal="Correct wrong information using the text.",
        student_instruction="Correct the wrong sentences.",
        l3_support="Use only if strongly scaffolded.",
        l4_support="Good A2 activity; one wrong fact per sentence.",
        required_fields=("wrong_sentence", "correct_sentence", "evidence"),
        min_items=4,
        min_level=4,
        priority=20,
    ),
    "reading_cause_effect": WorksheetActivity(
        code="reading_cause_effect",
        page=6,
        module="Reading",
        goal="Connect an event, reason, or result from the text.",
        student_instruction="Write what happens next.",
        l3_support="Use simple next-event logic.",
        l4_support="May use cause/effect wording when text supports it.",
        required_fields=("cause", "effect"),
        min_items=4,
        text_type="any",
        priority=45,
    ),
    "reading_short_answer": WorksheetActivity(
        code="reading_short_answer",
        page=6,
        module="Reading",
        goal="Write short text-supported answers.",
        student_instruction="Read the passage. Write short answers.",
        l3_support="One to three words or a short phrase.",
        l4_support="Short complete sentences when possible.",
        required_fields=("question", "answer", "evidence"),
        min_items=4,
        priority=35,
    ),

    # Page 7: Graphic organizer. These are recorded for QA/TG alignment.
    "go_sequence_chart": WorksheetActivity(
        code="go_sequence_chart",
        page=7,
        module="Graphic Organizer",
        goal="Organize events or steps in order.",
        student_instruction="Fill in the graphic organizer.",
        l3_support="Prefill key events and provide a word bank.",
        l4_support="Ask students to complete more labels or short phrases.",
        required_fields=("labels", "word_bank", "fillable_fields"),
        min_items=3,
        text_type="fiction",
        priority=10,
    ),
    "go_problem_plan_result": WorksheetActivity(
        code="go_problem_plan_result",
        page=7,
        module="Graphic Organizer",
        goal="Organize a story by problem, plan/action, and result.",
        student_instruction="Fill in the graphic organizer.",
        l3_support="Prefill one or two boxes and provide short options.",
        l4_support="Use fewer hints and more complete phrases.",
        required_fields=("labels", "word_bank", "fillable_fields"),
        min_items=3,
        text_type="fiction",
        priority=20,
    ),
    "go_fact_web": WorksheetActivity(
        code="go_fact_web",
        page=7,
        module="Graphic Organizer",
        goal="Organize facts about one topic.",
        student_instruction="Fill in the graphic organizer.",
        l3_support="Use a central topic and short fact options.",
        l4_support="Students write more complete fact phrases.",
        required_fields=("topic", "facts", "fillable_fields"),
        min_items=3,
        text_type="non-fiction",
        priority=10,
    ),
    "go_compare_chart": WorksheetActivity(
        code="go_compare_chart",
        page=7,
        module="Graphic Organizer",
        goal="Compare two people, places, animals, or ideas from the book.",
        student_instruction="Fill in the graphic organizer.",
        l3_support="Provide clear labels and a word bank.",
        l4_support="Ask for short evidence-based phrases.",
        required_fields=("labels", "word_bank", "fillable_fields"),
        min_items=3,
        priority=50,
        optional=True,
    ),

    # Page 8: Writing. Current renderer uses these as policy labels.
    "writing_sentence_starters": WorksheetActivity(
        code="writing_sentence_starters",
        page=8,
        module="Writing",
        goal="Write short responses with sentence starters.",
        student_instruction="Write about the book.",
        l3_support="Use 2-3 sentence starters and a word bank.",
        l4_support="Use fewer starters and connect ideas.",
        required_fields=("sentence_starters", "writing_lines"),
        min_items=2,
        priority=10,
        requires_unique_answer=False,
    ),
    "writing_organizer_to_writing": WorksheetActivity(
        code="writing_organizer_to_writing",
        page=8,
        module="Writing",
        goal="Use the organizer to write connected sentences.",
        student_instruction="Use your organizer to write.",
        l3_support="Write 2-3 supported sentences.",
        l4_support="Write 3-5 connected sentences.",
        required_fields=("organizer_reference", "sentence_starters", "writing_lines"),
        min_items=2,
        priority=20,
        requires_unique_answer=False,
    ),
}


def activity(code: str) -> WorksheetActivity:
    """Return a configured activity, raising a clear error for bad codes."""
    return L34_WORKSHEET_ACTIVITIES[code]


def instruction(code: str, fallback: str = "") -> str:
    item = L34_WORKSHEET_ACTIVITIES.get(code)
    return item.student_instruction if item else fallback


def page_activity_codes(page: int, *, include_optional: bool = False) -> list[str]:
    return [
        item.code
        for item in L34_WORKSHEET_ACTIVITIES.values()
        if item.page == page and (include_optional or not item.optional)
    ]


def allowed_activity_codes(
    page: int,
    *,
    level: int,
    text_type: str = "any",
    include_optional: bool = False,
) -> list[str]:
    normalized_type = "non-fiction" if "non" in (text_type or "").lower() else "fiction"
    rows = []
    for item in L34_WORKSHEET_ACTIVITIES.values():
        if item.page != page:
            continue
        if item.optional and not include_optional:
            continue
        if not (item.min_level <= level <= item.max_level):
            continue
        if item.text_type not in ("any", normalized_type):
            continue
        rows.append(item)
    rows.sort(key=lambda x: (x.priority, x.code))
    return [x.code for x in rows]


def activity_required_fields(code: str) -> tuple[str, ...]:
    item = L34_WORKSHEET_ACTIVITIES.get(code)
    return item.required_fields if item else ()


def activity_min_items(code: str, default: int = 4) -> int:
    item = L34_WORKSHEET_ACTIVITIES.get(code)
    return item.min_items if item else default
