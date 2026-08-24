# Architecture DSL Format Comparison

When designing a strict Architecture DSL for RepoLens (Phase 4), choosing the right configuration format is critical. The format must balance human readability, ease of authoring, machine strictness, and tooling support.

## YAML vs. JSON

### YAML (Recommended for Human Authoring)

**Advantages:**
*   **Human Readability & Less Noise:** Avoids the heavy syntax of JSON (brackets, braces, commas, and mandatory double quotes). An architecture DSL should be as easy to read as a playbook.
*   **Comments:** Natively supports `# comments`. This is critical for architecture files to document *why* a specific boundary exists.
*   **Multi-line Strings:** Allows clean multi-line strings (`|` or `>`) for including descriptions or rationales inside the DSL.
*   **Anchors and Aliases (`&` and `*`):** Supports DRY (Don't Repeat Yourself) principles. If multiple modules share the exact same `allowed_imports` list, it can be defined once and referenced.

**Disadvantages:**
*   **Strictness and Parsing Complexity:** The YAML specification is massive, and slight indentation mistakes can completely alter meaning or break the parser.
*   **Implicit Typing (The "Norway Problem"):** YAML attempts to automatically guess types (e.g., `NO` becomes a boolean `false`, `22` becomes an integer). This can lead to subtle bugs if a module name happens to be interpreted as a boolean or number.

### JSON (Recommended for Machine Generation)

**Advantages:**
*   **Strictness and Parsing:** JSON is rigid, strict, and its parsing is unambiguous. If a JSON file is valid, there is exactly one way to interpret it.
*   **Explicit Typing:** A string is always in quotes `"NO"`, preventing implicit type casting issues.
*   **Tooling and Schema Validation:** JSON is the native language of schemas, IDE autocomplete, and tooling. It is the safest format for programmatically generating configurations.

**Disadvantages:**
*   **No Comments:** JSON does not support comments natively, making it impossible to document architectural decisions within the file.
*   **Visual Noise:** Heavy use of quotes, commas, and braces makes it harder for humans to read and write quickly.

---

## Alternative Formats

Beyond YAML and JSON, several other formats could serve as the foundation for an Architecture DSL:

### 1. TOML (Tom's Obvious, Minimal Language)
Since RepoLens already uses TOML for `pyproject.toml` and `.repolens.example.toml`, this is a strong contender.
*   **Advantages:** Extremely unambiguous. Supports comments natively. Great for flat configurations. Strongly typed (strings require quotes).
*   **Disadvantages:** Deeply nested structures (which are common in architectural dependency mapping) can become verbose and visually cluttered compared to YAML's indentation-based nesting.

### 2. JSONC (JSON with Comments)
*   **Advantages:** Brings the strictness and tooling ecosystem of JSON but adds support for `//` and `/* */` comments. VS Code uses this heavily for `settings.json`.
*   **Disadvantages:** Not officially standardized. Standard JSON parsers will fail on it, requiring specific JSONC parsing libraries in Python.

### 3. HCL (HashiCorp Configuration Language)
Used by Terraform, HCL is designed specifically for defining infrastructure and architecture declaratively.
*   **Advantages:** Highly structured, supports comments, and handles complex nested blocks elegantly. Great for defining resources and relationships.
*   **Disadvantages:** Less ubiquitous than YAML/JSON. Requires importing specific HCL parsing libraries which might bloat the RepoLens CLI dependencies.

### 4. Custom DSL (e.g., Sonargraph `.arc`)
Instead of using a general-purpose data format, RepoLens could implement a custom parser (like Zügel does with Sonargraph's `.arc` files).
*   **Advantages:** Can be perfectly tailored to the domain. E.g., `module "api" cannot depend on "database"`. Extremely readable.
*   **Disadvantages:** Very high engineering cost. You lose all free tooling (JSON Schema IDE autocomplete, syntax highlighting, standard library parsers).

### 5. Python / Code-as-Config (e.g., `repolens.py`)
Defining the architecture in Python itself (similar to how Pulumi or AWS CDK work).
*   **Advantages:** Ultimate flexibility. Developers can use loops, variables, and logic to define rules.
*   **Disadvantages:** Security risks (executing arbitrary code during a scan). Harder for non-Python developers to write. Harder for LLMs to safely parse and modify compared to declarative data formats.

---

## Conclusion & Recommendation

For Phase 4, **YAML backed by a strict JSON Schema** remains the strongest candidate. 
* It provides the comments and readability required for a human-centric architectural playbook.
* The JSON Schema ensures that IDEs (VS Code, Cursor, JetBrains) provide instant autocomplete, validation, and tooltips while developers type, mitigating YAML's lack of strictness.
* It is widely understood by LLMs, making it easy for the RepoLens MCP server to read, write, and reason about the architecture.
