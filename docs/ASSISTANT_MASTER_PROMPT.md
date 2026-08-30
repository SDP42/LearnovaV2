# Learnova — Assistant Layer Master Prompt

> Governing spec for the AI Assistant Layer (voice + chat + presentation
> intelligence + QA knowledge system). Pairs with `docs/MASTER_PROMPT.md`
> (content preservation) — the assistant never auto-summarises Learnova
> content; it summarises *its own reply* only when the user asks.

## Core principle

The assistant is **the intelligent control layer for the Learnova learning
environment**, not a Q&A chatbot. Natural language in → correct Learnova
action or answer out. The user never learns a command language.

```
User → Voice/Text → Intent → Entities → Context → Action plan →
Learnova tools/APIs/content → Response → Text + Voice + UI action
```

Two request classes, handled differently:

- **Information requests** — "Explain RSA." → answer from Learnova content.
- **Action requests** — "Open presentation 2." / "Go to slide 5." /
  "Give me the web deck." → resolve → validate → execute a structured action.

## Non-negotiables

1. **Not a simple `question → LLM → text` bot.** It is an orchestration
   layer: intent classification → entity extraction → context retrieval →
   permission/validation → action selection → tool execution → NL response →
   UI update / voice.
2. **Stable presentation IDs.** Every deck has a permanent `LRN-PRES-NNNN`
   id. Display numbers are a user-facing convenience and are always resolved
   to the permanent id before any action. Never couple actions to display
   numbers. Never trust an LLM-generated id — the backend validates existence
   + permission before executing.
3. **Natural references resolve through the registry**: direct id, number,
   title, partial title, position, description, "the one we looked at
   earlier". Ambiguous → ask, don't guess.
4. **Tool-based actions.** The LLM chooses a tool; the tool performs the
   operation. `LLM → structured action → backend validation → permission →
   DB lookup → execute`.
5. **Context awareness.** Session holds `current_presentation`,
   `current_slide`, `previous_slide`, `current_subject/topic`,
   `last_user_request`, `last_referenced_entity`, `conversation_context`,
   `active_mode`. "Explain this" / "go back" / "the second one" resolve
   against it.
6. **Confidence-aware.** High → execute. Medium → execute if safe, else
   confirm. Low → ask for clarification.
7. **Graceful failure.** Presentation/slide/resource missing, unauthorized,
   unsupported action, transcription error, API/network failure → a useful
   explanation, never a fabricated result, never "not in my dataset".
8. **Never hallucinate Learnova content.** Not found → say so; offer a
   general explanation or to add the content.
9. **Voice = natural speech, concise replies.** "Opening presentation two."
   not "Certainly! I would be delighted…". Support stop / pause / resume /
   repeat / cancel where technically possible.
10. **Content vs response language** are separate axes. "Explain in Hindi"
    changes the reply, never the stored content.

## Structured response protocol

Every assistant turn returns a typed response, e.g.

```json
{ "type": "OPEN_PRESENTATION", "presentation_id": "LRN-PRES-0002",
  "message": "Opening presentation 2." }
```

Response types: `TEXT_RESPONSE · OPEN_PRESENTATION · OPEN_SLIDE · NAVIGATE ·
SHOW_WEB_DECK · PLAY_ANIMATION · SHOW_VISUAL · START_QUIZ ·
SHOW_SEARCH_RESULTS · CREATE_PRESENTATION · SEARCH_CONTENT · EXPLAIN_CONTENT ·
ASK_CLARIFICATION · ERROR_RESPONSE` (+ combined, e.g. `EXPLAIN_AND_NAVIGATE`).

## Intent taxonomy (minimum)

Presentation: `CREATE_PRESENTATION OPEN_PRESENTATION VIEW_PRESENTATION
SEARCH_PRESENTATION GET_PRESENTATION GET_WEB_DECK OPEN_WEB_DECK
START_PRESENTATION STOP_PRESENTATION RESUME_PRESENTATION RESTART_PRESENTATION
NEXT_SLIDE PREVIOUS_SLIDE GO_TO_SLIDE FIRST_SLIDE LAST_SLIDE
SEARCH_WITHIN_PRESENTATION SUMMARIZE_PRESENTATION EXPLAIN_PRESENTATION`
(summarise only on explicit user request).

Slide: next / back / go-to-N / go-to-named-section / repeat / explain-this /
read-this / explain-this-diagram.

Educational: `EXPLAIN_CONCEPT COMPARE_CONCEPTS GIVE_EXAMPLE SIMPLIFY
STEP_BY_STEP WHY_QUESTION WHAT_NEXT REAL_WORLD_EXAMPLE`.

Learning: `TEACH_TOPIC START_QUIZ NEXT_QUIZ_QUESTION SUBMIT_QUIZ_ANSWER
EXPLAIN_MISTAKE EASIER_EXAMPLE HARDER_EXAMPLE EXAM_PREP`.

Content: `SEARCH_CONTENT WHERE_IS_TOPIC FIND_PRESENTATIONS_ABOUT`.

Visualisation: `MAKE_VISUAL ADD_ANIMATION MAKE_INTERACTIVE VISUALISE_PROCESS`.

System: `HELP CAPABILITIES SETTINGS`. Meta: `AMBIGUOUS UNKNOWN`.

## Tools (structured functions the orchestrator calls)

`searchPresentations · getPresentation · openPresentation · getWebDeck ·
openSlide · goToSlide · searchContent · getSlideContent · explainContent ·
createPresentation · createVisual · startQuiz · getQuizQuestion ·
submitQuizAnswer`.

## QA / intent dataset

~1000–2000 realistic examples (not random), categorised, each with:
`id · category · intent · question · variants[] · entities · expected_action
· requires_context · requires_presentation · answer_type · response`.
Lives as project data under `data/assistant/`. It is the **coverage
foundation and benchmark**, not a hard boundary — the assistant must handle
unseen requests by combining intent + context + retrieval + tools + metadata.

Benchmark metrics: intent accuracy, entity-extraction accuracy,
presentation-resolution accuracy, action accuracy, context accuracy,
clarification accuracy, response correctness, voice-command accuracy.

## Build sequence

1 inspect · 2 architecture · 3 presentation registry + stable ids ·
4 intent + entity system · 5 tool/API layer · 6 context/session ·
7 chat assistant · 8 voice (STT/TTS) · 9 QA dataset (~1–2k) ·
10 automated intent/action tests · 11 edge cases · 12 UX polish.

## Frontend / backend split

Frontend: mic, speech playback, chat UI, assistant UI, navigation, visual
response, animations, action execution.
Backend: intent processing, LLM orchestration, context, presentation lookup,
content retrieval, authorization, action validation, dataset, session
memory, API integration, tool execution.

## Do not

- overengineer before inspecting the existing stack
- add new tech where existing tech suffices
- put assistant intelligence in the frontend
- optimise only for the benchmark questions
