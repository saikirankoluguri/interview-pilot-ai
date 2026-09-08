# Interview flow

The local mock implementation exercises this complete sequence without a model or
external service:

1. Setup validates name, role, optional company, PDF resume, pasted JD, round,
   difficulty, duration, and panel size.
2. The engine creates a private UUID session, saves it atomically, obtains a
   strategy/panel, and starts the server timer.
3. The interviewer greeting and opening question are converted to audio.
4. After playback, the microphone listens. VAD automatically identifies a complete
   candidate turn; there is no answer textbox or submit-answer button.
5. STT creates an internal transcript. The engine records it against the current
   question before evaluation.
6. One structured live call returns hidden evaluation, action, next difficulty,
   and next question.
7. The deterministic adaptive policy validates/clamps difficulty. The question
   router prevents repeats and excessive topic runs.
8. TTS creates interviewer audio, the UI changes to Interviewer speaking, and the
   cycle repeats. No score, transcript, rationale, missing concept, coaching, or
   ideal answer is shown live.
9. The server timer or End Interview moves the session to Ending. Final evaluation
   covers every asked question, including an unanswered last question without
   treating it as assessed performance.
10. The final JSON report is saved, the session becomes Completed, and the feedback
    tab shows category scores, each question/transcript, strengths, missing points,
    expected concepts, better answers, preparation topics, and next focus.

```text
Setup -> greeting audio -> Listening -> VAD -> STT -> Processing
  ^                                                   |
  |          next question audio <- TTS <- one live decision
  |                                                   |
  +---------------- repeat ----------------------------+
                               |
                         End -> final report -> feedback
```

Local mocks deliberately use silence, a fixed transcript, and a score cycle. They
verify orchestration only. Lightning must validate real speech and the 1-4 second
latency goal. Difficulty never uses accent, speaking speed/style, voice pitch,
emotion, gender, facial expression, personality, or perceived honesty.