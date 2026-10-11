# LinkedIn Post: Introducing RepoLens

**Target Audience:** Fractional CTOs, Principal Engineers, Engineering Directors, Technical Consultants, M&A Auditors  
**Website Link:** [CycleRunCode Club](https://cycleruncode.club)  
**Repository Link:** [GitHub - RepoLens](https://github.com/vksvicky/RepoLens)

---

### Post Copy (Ready to copy/paste)

Every time I’ve had to do technical due diligence on an inherited codebase, I’ve run into the exact same three frustrations:

1. SonarQube is great for continuous inspection, but I’m not spending 3 hours provisioning a server and PostgreSQL just to audit a repository for a 48-hour deadline.
2. SaaS AI review bots are slick, but enterprise clients with proprietary IP or strict NDAs won't let you pipe their source code through a third-party webhook cloud.
3. Chaining Semgrep, Trivy, and Gitleaks in bash gives you three disconnected JSON dumps that no VP of Engineering wants to read.

We built RepoLens to fix this. It's part of what we teach and build at CycleRunCode Club (https://cycleruncode.club).

It’s an open-source CLI built for zero-infrastructure code audits:
• Fast Brain (sub-second): Runs deterministic SAST/SCA scanners + flags circular module dependencies (Python & polyglot tree-sitter) + checks layer boundaries.
• Slow Brain: Runs structured, multi-pass AI audits (P1 Security → P2 Reliability → P3 Architecture) with concrete fix snippets.
• 100% Zero-Infra: Runs on your laptop via local Ollama or private BYOK (Bedrock, Vertex, Gemini). Zero data leaves your machine.

We recently dogfooded a 500-file repo and learned a hard lesson about LLMs: when a local 32B model emitted valid findings but left `codeExample: null` on a High finding, our Pydantic validator crashed the pass, which zeroed out the entire audit gate score! 

Lesson learned: Never let tool packaging noise masquerade as a code defect. We hardened the coercion layer, decoupled deterministic scanner gates from AI synthesis, and built dedicated presets:
- `repolens review --preset pr`: Deterministic, <2s, 0 LLM (CI-ready)
- `repolens review --preset release`: Deep multi-role due diligence

If you consult, audit, or manage pre-release gates, give it a spin:
`pipx install repolens-audit`

Explore the project:
• GitHub: https://github.com/vksvicky/RepoLens
• Playbooks & Frameworks: https://cycleruncode.club

Curious how other consultants handle rapid due diligence without standing up servers? Let me know in the comments.

#SoftwareEngineering #CodeReview #CyberSecurity #DevOps #FractionalCTO #TechDueDiligence #OpenSource #Python
