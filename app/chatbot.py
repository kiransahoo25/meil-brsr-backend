"""Rule-based chatbot for the MEIL BRSR Portal.

Answers user questions using keyword matching against a knowledge base.
Role-aware: some answers are tailored to what the user can actually do.
"""


# Each entry: keywords (any match triggers), answer (default), answers_by_role (optional overrides)
KNOWLEDGE = [
    {
        "keywords": ["hello", "hi ", "hey", "good morning", "good evening", "namaste"],
        "answer": "Hello! 👋 I'm your BRSR assistant. Ask me anything about the portal — how to enter data, submit for approval, download reports, or what a term means.",
    },
    {
        "keywords": ["what is brsr", "brsr meaning", "brsr stand for", "define brsr"],
        "answer": "**BRSR** = Business Responsibility and Sustainability Report. It's a mandatory disclosure format introduced by SEBI (Securities and Exchange Board of India) for the top 1,000 listed companies. It covers 9 principles (NGRBC) across Environment, Social, and Governance topics, plus 46 BRSR Core KPIs that need independent assurance.",
    },
    {
        "keywords": ["ngrbc", "9 principles", "nine principles", "principle 1", "principle 3", "principle 6", "principle 8"],
        "answer": "The **9 NGRBC Principles** are:\n1. Ethics & Transparency\n2. Sustainable products & services\n3. Employee wellbeing\n4. Stakeholder engagement\n5. Human rights\n6. Environment\n7. Public policy advocacy\n8. Inclusive growth\n9. Customer value\n\nIn this portal we collect data for **P1, P3, P6, P8** and the **BRSR Core** (9 attributes, 46 KPIs).",
    },
    {
        "keywords": ["what is sdg", "sdg meaning", "sustainable development goals", "un sdg"],
        "answer": "**SDG** = Sustainable Development Goals — 17 goals set by the United Nations for 2030. MEIL prioritises **8 goals**: SDG 6 (Clean Water), 7 (Clean Energy), 8 (Decent Work), 9 (Infrastructure), 11 (Sustainable Cities), 13 (Climate Action), 16 (Governance), and 17 (Partnerships). You can view alignment scores in the **SDG Report** page.",
    },
    {
        "keywords": ["enter data", "fill data", "input data", "add data", "where to type"],
        "answers_by_role": {
            "data-entry": "Go to **BRSR Data Collection** in the sidebar. Pick a section on the left (e.g. Principle 6), fill in the fields, and click **✓ Submit All Sections** at the top when done. Everything saves automatically as you type.",
        },
        "answer": "Data entry is done by the **Data Entry Operator** for each unit. If you're a Data Entry user, go to **BRSR Data Collection**. If you're an Approver or above, your role is to review what they submit via **Approvals**.",
    },
    {
        "keywords": ["submit", "how to submit", "send for review", "send for approval"],
        "answers_by_role": {
            "data-entry": "After filling in fields, click **✓ Submit All Sections** at the top-right of the Collection page. All sections with complete required fields will be sent to your Entity Approver. Sections with missing fields will be skipped — you'll see a message telling you which ones.",
        },
        "answer": "Submissions are made by Data Entry Operators from the **BRSR Data Collection** page. As your role, you'll see incoming submissions in the **Approvals** section.",
    },
    {
        "keywords": ["approve", "how to approve", "review submission"],
        "answers_by_role": {
            "approver": "Go to **Approvals** in the sidebar. You'll see a table of submissions. Click **View** on any row to see the full data. Inside the modal, you can **Approve**, **Request Changes**, or **Reject**. You can also comment to ask the operator for clarification.",
            "unit-admin": "Go to **Approvals** in the sidebar. Click **View** on any submission to see the full data, then choose **Approve**, **Request Changes**, or **Reject**.",
        },
        "answer": "Approval actions are available to Entity Approvers, Unit Admins, ESG Officers and Group Admins via the **Approvals** page.",
    },
    {
        "keywords": ["reject", "request change", "send back", "ask for change"],
        "answer": "In **Approvals** → click **View** on a submission → click **Request Changes** to send it back with a remark, or **Reject** for data that can't be corrected. You can also add a comment explaining what's wrong — the data-entry operator will see it.",
    },
    {
        "keywords": ["comment", "add comment", "flag issue", "ping"],
        "answer": "Open any submission in the **Approvals** page → click **View** → click **💬 Comments** in the top bar of the modal. Type your message and click **Send Comment**. The comment is visible to everyone who opens that submission — it's the fastest way to flag an issue to a specific unit.",
    },
    {
        "keywords": ["download pdf", "export pdf", "brsr report pdf", "download report"],
        "answer": "Go to **ESG Report** in the sidebar → click **⬇ Download BRSR PDF** at the top-right. This generates a 4-page PDF with a cover, executive summary, environmental charts, and social/governance tables. The **SDG Report** page has a similar **⬇ Download SDG PDF** button for the UN SDG report.",
    },
    {
        "keywords": ["esg report", "esg score", "environmental social governance"],
        "answer": "The **ESG Report** page shows your BRSR performance broken into three pillars:\n• **E — Environmental** (emissions, energy, water, waste)\n• **S — Social** (employees, safety, community)\n• **G — Governance** (ethics, board, transparency)\n\nEach pillar gets a score based on how many BRSR fields have been completed in the relevant principles.",
    },
    {
        "keywords": ["validation", "check errors", "data error", "exception"],
        "answer": "The **Validation Center** runs automated rules on every datapoint — checking for missing required fields, percentage out of bounds, negative values, implausible numbers, and cross-section mismatches. Click **⚡ Run Validation** to scan, and **Resolve** on any issue after you've fixed the underlying data.",
    },
    {
        "keywords": ["audit trail", "who changed", "history", "log"],
        "answer": "The **Audit Trail** page shows every change made in the portal — who edited what, when, and the before/after values. It's append-only, so nothing can be deleted. You can filter by action type, search by user or datapoint, and export the full log as CSV.",
    },
    {
        "keywords": ["evidence", "attach file", "upload", "proof"],
        "answer": "Certain high-value fields (emissions, fatalities, CSR, GHG intensity) have an **📎 Attach Evidence** button. Click it to attach a PDF, image, or spreadsheet that supports the value — invoices, meter readings, signed declarations. This is required for BRSR Core assurance.",
    },
    {
        "keywords": ["deadline", "due date", "when due", "last date"],
        "answer": "The current reporting cycle (FY 2025-26) is due in **27 days**. You'll see a countdown badge in the top-right corner of every page. Sections with incomplete fields will be flagged as the deadline approaches.",
    },
    {
        "keywords": ["who can see", "who sees my data", "privacy", "access"],
        "answer": "Data access is role-based:\n• **Data Entry** — only their own unit's data\n• **Entity Approver** — their unit's submissions for review\n• **Unit Admin** — their unit's full reports\n• **ESG Officer** — all 11 units + cross-unit consolidated view\n• **Group Admin** — everything, including user management",
    },
    {
        "keywords": ["olestra", "olectra"],
        "answer": "**Olectra Green Tech** is one of MEIL's 4 subsidiaries. It's consolidated into the group BRSR report and shows up in the Consolidated View and unit dropdowns. The Data Entry Operator for Olectra is Sunita Rao (code A9).",
    },
    {
        "keywords": ["forgot password", "reset password", "change password", "cant login", "can't login"],
        "answer": "Passwords are managed by the **Group Admin (E1)**. Contact Sanjay Kulkarni or your portal administrator to reset it. For demo purposes, all accounts use the password `demo`.",
    },
    {
        "keywords": ["logout", "sign out", "log out", "exit"],
        "answer": "Click **⏻ Sign Out** in the sidebar (top-left area, right below your name). The portal also auto-signs you out after **3 minutes of inactivity** — you'll see a 15-second warning before that happens.",
    },
    {
        "keywords": ["language", "hindi", "translate"],
        "answer": "The portal is currently in English. The BRSR report PDFs contain the standard SEBI terminology. Hindi / regional language support is planned for a future release.",
    },
    {
        "keywords": ["data safe", "security", "secure", "encryption"],
        "answer": "Yes. Data is transmitted over HTTPS, passwords are hashed with bcrypt, sessions use signed JWTs, and the database (Neon) encrypts at rest. Every change is logged in the Audit Trail with a timestamp and user code — nothing can be deleted or edited retroactively.",
    },
    {
        "keywords": ["mobile", "phone", "tablet"],
        "answer": "Yes! The portal works on phones and tablets. On small screens, tap the ☰ hamburger icon in the top-left to open the sidebar menu. Everything else scales automatically.",
    },
    {
        "keywords": ["help", "how do i", "how to", "what do i", "guide", "tutorial"],
        "answer": "I can help with:\n• Filling in BRSR data\n• Submitting for review\n• Approving or rejecting submissions\n• Downloading the BRSR / SDG PDF reports\n• Understanding a term (BRSR, SDG, NGRBC)\n• Fixing validation errors\n\nJust type your question in plain English!",
    },
    {
        "keywords": ["thanks", "thank you", "thx", "great", "awesome", "nice"],
        "answer": "You're welcome! 😊 Anything else I can help with?",
    },
]


GREETINGS_BY_ROLE = {
    "data-entry": "Hi! I'm your BRSR assistant. Ask me how to fill in data, submit for review, or what a term means.",
    "approver": "Hi! I can help you understand submissions, approval flow, or how to flag issues to a unit.",
    "unit-admin": "Hi! Ask me about your unit's reports, the approval workflow, or how to drill into ESG / SDG data.",
    "esg-officer": "Hi! Ask me about cross-unit review, the consolidated view, or how to comment on a submission.",
    "group-admin": "Hi! I can help with equity share, action points, group-wide reports, and portal administration.",
}


def _score_match(question: str, keywords: list) -> int:
    """Return a score for how well the question matches the keywords."""
    q = question.lower().strip()
    score = 0
    for kw in keywords:
        if kw in q:
            score += len(kw)
    return score


def find_answer(question: str, role: str) -> str:
    """Given a user question and their role, return the best answer."""
    if not question or not question.strip():
        return "Please type a question and I'll do my best to help."

    q = question.lower()

    # Score every entry, pick the highest
    best_entry = None
    best_score = 0
    for entry in KNOWLEDGE:
        s = _score_match(q, entry["keywords"])
        if s > best_score:
            best_score = s
            best_entry = entry

    if best_entry and best_score > 0:
        # Role-specific override if it exists
        if "answers_by_role" in best_entry:
            role_answer = best_entry["answers_by_role"].get(role)
            if role_answer:
                return role_answer
        return best_entry["answer"]

    # No match — give a helpful fallback
    return (
        "I'm not sure about that one. I can help with:\n"
        "• How to fill in BRSR data\n"
        "• Submitting for review\n"
        "• Approving or rejecting submissions\n"
        "• Downloading PDF reports\n"
        "• Explaining BRSR, SDG, NGRBC terms\n"
        "• Fixing validation errors\n\n"
        "Try rephrasing, or ask 'help' to see the list again."
    )


def get_greeting(role: str) -> str:
    return GREETINGS_BY_ROLE.get(role, "Hi! I'm your BRSR assistant. How can I help?")


SUGGESTIONS_BY_ROLE = {
    "data-entry": [
        "How do I fill in data?",
        "How do I submit?",
        "What does BRSR mean?",
        "What is the deadline?",
    ],
    "approver": [
        "How do I approve a submission?",
        "How do I flag an issue?",
        "How do I request changes?",
    ],
    "unit-admin": [
        "How do I download the PDF?",
        "How do I add evidence?",
        "What is the ESG report?",
    ],
    "esg-officer": [
        "How do I review all units?",
        "How do I comment on a submission?",
        "What is the consolidated view?",
    ],
    "group-admin": [
        "How do I export the audit trail?",
        "What is the equity share?",
        "How do I run validation?",
    ],
}


def get_suggestions(role: str) -> list:
    return SUGGESTIONS_BY_ROLE.get(
        role,
        ["How do I submit data?", "What is BRSR?", "How do I download a PDF?"],
    )