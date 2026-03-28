VALID_CATEGORIES = {
    "1. Code Authoring": [
        "1.1 New Implementation",
        "1.2 Iterative Modification",
        "1.3 Alignment Correction",
    ],
    "2. Failure Reporting": [
        "2.1 Log Paste",
        "2.2 Symptom Description",
        "2.3 Error Persistence",
    ],
    "3. Inquiry": [
        "3.1 Planning & Decision Consultation",
        "3.2 Project Comprehension",
        "3.3 General Knowledge Query",
    ],
    "4. Context Specification": [
        "4.1 Information Injection",
        "4.2 Behavior Specification",
    ],
    "5. Validation": [
        "5.1 Code Review",
        "5.2 Runtime Inspection",
    ],
    "6. Delegation": [
        "6.1 Documentation",
        "6.2 Toolchain Operation",
    ],
    "7. Workflow Control": [
        "7.1 Confirmation",
        "7.2 Continuation",
        "7.3 Deferred Debugging",
        "7.4 Deferred Implementation",
        "7.5 Sentiment Expression",
    ],
    "8. Others": ["8.1 Others"],
}

VALID_LABELS = {(main, sub) for main, subs in VALID_CATEGORIES.items() for sub in subs}
