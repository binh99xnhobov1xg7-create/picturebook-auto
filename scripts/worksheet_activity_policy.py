"""L3/L4 worksheet activity taxonomy.

This file is intentionally declarative. The worksheet builder uses these
activity codes to keep page goals explicit, avoid vague task labels, and record
which activity type was selected for QA or later TG-only generation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorksheetActivity:
    code: str
    page: int
    module: str
    goal: str
    student_instruction: str
    l3_support: str
    l4_support: str
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
    ),
    "vocab_word_picture_matching": WorksheetActivity(
        code="vocab_word_picture_matching",
        page=1,
        module="Vocabulary",
        goal="Match core words with pictures.",
        student_instruction="Match each word with the picture.",
        l3_support="Use pictures for each core word.",
        l4_support="Use pictures only when the word is visually clear.",
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
    ),
    "vocab_contextual_choice": WorksheetActivity(
        code="vocab_contextual_choice",
        page=2,
        module="Vocabulary",
        goal="Choose the core word that fits a context clue.",
        student_instruction="Read each clue and circle the correct word.",
        l3_support="Two or three choices; concrete clues.",
        l4_support="Three choices; clues may use function or context.",
    ),
    "vocab_contextual_clue_write": WorksheetActivity(
        code="vocab_contextual_clue_write",
        page=2,
        module="Vocabulary",
        goal="Write the core word from a context or meaning clue.",
        student_instruction="Read the clue and write the word.",
        l3_support="Word bank or first-letter support preferred.",
        l4_support="May omit the full word bank when clues are clear.",
    ),
    "vocab_multi_word_cloze": WorksheetActivity(
        code="vocab_multi_word_cloze",
        page=2,
        module="Vocabulary",
        goal="Use a complete core phrase in context.",
        student_instruction="Use the phrases to fill each blank.",
        l3_support="Keep phrases intact; provide full phrase bank.",
        l4_support="Use story context to choose complete phrases.",
    ),
    "vocab_category_sorting": WorksheetActivity(
        code="vocab_category_sorting",
        page=2,
        module="Vocabulary",
        goal="Sort core words by meaning or use.",
        student_instruction="Sort the words.",
        l3_support="Two simple categories.",
        l4_support="More precise categories when the word set supports it.",
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
    ),
    "sentence_correct_sentence_choice": WorksheetActivity(
        code="sentence_correct_sentence_choice",
        page=3,
        module="Sentence",
        goal="Choose the grammatically correct sentence.",
        student_instruction="Choose the correct sentence.",
        l3_support="Two choices; visible support when useful.",
        l4_support="Three choices when the contrast is clear.",
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
    ),
    "sentence_complete_frame": WorksheetActivity(
        code="sentence_complete_frame",
        page=4,
        module="Sentence",
        goal="Complete the syllabus sentence frame.",
        student_instruction="Complete the sentence frame.",
        l3_support="Fill one or two blanks only.",
        l4_support="May complete a longer phrase if the frame supports it.",
    ),
    "sentence_guided_writing": WorksheetActivity(
        code="sentence_guided_writing",
        page=4,
        module="Sentence",
        goal="Write single sentences with strong sentence-frame support.",
        student_instruction="Write one sentence for each prompt.",
        l3_support="Full frame, keyword, and long writing line.",
        l4_support="Frame or starter; still single-sentence practice.",
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
    ),
    "sentence_reorder_words": WorksheetActivity(
        code="sentence_reorder_words",
        page=4,
        module="Sentence",
        goal="Put words in order to make the target sentence.",
        student_instruction="Put the words in order.",
        l3_support="Short sentences and full punctuation.",
        l4_support="Longer target-pattern sentences.",
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
    ),
    "reading_supported_sentence_choice": WorksheetActivity(
        code="reading_supported_sentence_choice",
        page=5,
        module="Reading",
        goal="Choose the sentence supported by the text.",
        student_instruction="Read the passage. Circle the correct sentence.",
        l3_support="Two or three choices; direct text support.",
        l4_support="Three choices with precise detail changes.",
    ),
    "reading_literal_mc": WorksheetActivity(
        code="reading_literal_mc",
        page=5,
        module="Reading",
        goal="Answer Who, What, Where, or When questions from the text.",
        student_instruction="Choose the correct answer.",
        l3_support="Mostly direct details.",
        l4_support="Can include more exact wording from the passage.",
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
    ),
    "reading_sequence_ordering": WorksheetActivity(
        code="reading_sequence_ordering",
        page=6,
        module="Reading",
        goal="Put story events or process steps in order.",
        student_instruction="Number the events in order.",
        l3_support="Four to five short events.",
        l4_support="Five events or process steps when supported by text.",
    ),
    "reading_text_based_correction": WorksheetActivity(
        code="reading_text_based_correction",
        page=6,
        module="Reading",
        goal="Correct wrong information using the text.",
        student_instruction="Correct the wrong sentences.",
        l3_support="Use only if strongly scaffolded.",
        l4_support="Good A2 activity; one wrong fact per sentence.",
    ),
    "reading_cause_effect": WorksheetActivity(
        code="reading_cause_effect",
        page=6,
        module="Reading",
        goal="Connect an event, reason, or result from the text.",
        student_instruction="Write what happens next.",
        l3_support="Use simple next-event logic.",
        l4_support="May use cause/effect wording when text supports it.",
    ),
    "reading_short_answer": WorksheetActivity(
        code="reading_short_answer",
        page=6,
        module="Reading",
        goal="Write short text-supported answers.",
        student_instruction="Read the passage. Write short answers.",
        l3_support="One to three words or a short phrase.",
        l4_support="Short complete sentences when possible.",
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
