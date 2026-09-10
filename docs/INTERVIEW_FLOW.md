# Interview flow

The local mock implementation exercises this complete sequence without a model or
external service:

1. Setup validates name, role, optional company, PDF resume, pasted JD, round,
   difficulty, duration, and panel size.
2. The engine creates a private UUID session, saves it atomically, obtains a
   strategy/panel, and starts the server timer.
3. Start Interview prepares the session, creates the interviewer greeting/opening
   question, synthesizes it, changes to the interview screen, and starts playback.
4. Microphone input is application-gated during interviewer playback. The playback
   completion event changes the voice state to Listening without a second click.
5. WebRTC chunks are normalized and buffered. VAD first detects meaningful speech,
   then configured silence automatically closes the candidate turn. Silence before
   speech does not submit an answer, and maximum answer duration is bounded.
6. STT creates an internal transcript. The engine records it against the current
   question before evaluation.
7. One structured live call returns hidden evaluation, action, next difficulty,
   and next question.
8. The deterministic adaptive policy validates/clamps difficulty. The question
   router prevents repeats and excessive topic runs.
9. TTS creates interviewer audio, the UI changes to Interviewer speaking, and the
   cycle repeats. No score, transcript, rationale, missing concept, coaching, or
   ideal answer is shown live.
10. The server timer or End Interview gates new input and moves the session to
    Ending. An in-flight turn may finish safely, then a natural closing is spoken.
    Final evaluation covers every asked question, including an unanswered last
    question without treating it as assessed performance.
11. The final JSON report is saved, the session becomes Completed after closing
    playback, and the feedback tab shows category scores, each
    question/transcript, strengths, missing points, expected concepts, better
    answers, preparation topics, and next focus.

```text
Setup -> Start -> greeting audio -> Listening -> Candidate speaking
                                      |                 |
                                      |       automatic silence detection
                                      |                 |
                                      +-- next audio <- TTS <- one live decision <- STT
                                                           |
                                           End/timer -> closing -> feedback
```

Local mocks deliberately use silence, a fixed transcript, and a score cycle. They
verify orchestration only. Lightning must validate real speech and the 1-4 second
latency goal. Difficulty never uses accent, speaking speed/style, voice pitch,
emotion, gender, facial expression, personality, or perceived honesty.

Empty/noisy transcription produces a deterministic repeat request without an LLM
call or recorded answer. VAD failure returns to listening where possible. The live
LLM retries once safely; TTS retries once. Candidate-facing errors never include
provider details or stack traces.
