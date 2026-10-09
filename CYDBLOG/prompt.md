Understood. **CYDBLOG is our agent-learning exercise:** the agents recreate the basic blog from requirements, while you keep the original as the reference for judging their work. My previous social-site backlog was too broad.

I inspected the uploaded files. Here’s the replacement backlog:

| PBI | Scope | Acceptance criteria |
|---|---|---|
| **1. Establish the application shell** | UI-HTML, UI-CSS | A single-page blog with browse, detail, and editor views. Teal header, light background, rounded cards, and a responsive grid: one column on phones, two on medium screens, three on larger screens. |
| **2. Load and display posts** | UI-JS | Load stored posts and show title, category, date, and a plain-text excerpt on each card. Default to newest first. Display loading, empty, and failure states. |
| **3. Filter and sort posts** | UI-HTML, UI-JS | Combine category and month filters. Support newest, oldest, and category ordering. Build filter options from existing posts and show when nothing matches. |
| **4. Read a complete post** | UI-HTML, UI-JS | Selecting a card opens its complete formatted content, title, category, and date. Provide Back and Edit actions. |
| **5. Create posts** | UI-HTML, UI-JS | Require title, category, date, and content. Suggest existing categories. Support bold, italic, underline, bulleted lists, numbered lists, and links. Cancel saves nothing. |
| **6. Persist and edit posts** | API, UI-JS | Publish new posts and update existing ones without duplicating them. Preserve other posts. Verify persistence after reload and show useful save errors. |
| **7. Verify the finished blog (Maintenance)** | Testing, UI-CSS | Verify the complete create → browse → filter → read → edit workflow, formatted content, keyboard navigation, responsive layout, and expandable JSON preview. Render content without executing scripts or unsafe links. |
| **8. Apply the small change** | To be determined | Define and verify your requested difference from the reference product. |

Give the agents these requirements and acceptance criteria, **without copying the original files into their accessible project folders**. Initially, let one agent implement one PBI at a time; you review the result before it proceeds. That makes its decisions and mistakes easier to follow.

**What is the one small change you want?** If it’s switching from CYD/WebDAV storage to a local Python server, we’ll specify that in PBI 6 rather than treating it as an extra feature.