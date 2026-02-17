# DevBots PlantUML Diagrams

This directory contains PlantUML architecture diagrams for the DevBots project.

## 📊 Available Diagrams

### 1. System Overview (`system-overview.puml`)
**Simple high-level view of the entire system**

Shows:
- 4 main bots (Orchestrator, GitBot, QABot, PMBot)
- Shared library components
- External services (Git, GitLab/GitHub, Claude AI)
- Report storage
- User interaction points

**Best for:** Getting a quick understanding of what DevBots is and how components relate.

### 2. Bot Architecture (`bot-architecture.puml`)
**Detailed component architecture diagram**

Shows:
- Internal structure of each bot
- Shared library modules (models, utilities, API clients)
- Data storage (reports, project registry)
- External system connections
- Detailed component relationships

**Best for:** Understanding the internal structure and dependencies between components.

### 3. Data Flow (`data-flow.puml`)
**Sequence diagram showing data transformations**

Shows:
- How data flows through each bot
- Model transformations (commits → ChangeSet, issues → IssueSet, etc.)
- Inter-bot data sharing (GitBot → QABot via ChangeSet)
- Orchestrator coordination workflow
- Report storage lifecycle

**Best for:** Understanding how data moves through the system and how bots collaborate.

### 4. Bot Interactions (`bot-interactions.puml`)
**Component diagram showing invocation patterns**

Shows:
- Bot API contracts (get_bot_result(), get_changeset(), etc.)
- CLI interfaces for each bot
- Orchestrator's bot invocation mechanism
- Inter-bot composition patterns
- Shared model dependencies

**Best for:** Understanding how to use and integrate bots programmatically.

## 🎨 Viewing the Diagrams

### Option 1: VS Code (Recommended)
1. Install the [PlantUML extension](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)
2. Open any `.puml` file
3. Press `Alt+D` to preview

### Option 2: Online
1. Go to [PlantUML.com](https://www.plantuml.com/plantuml/uml/)
2. Copy and paste the diagram code
3. View the rendered diagram

### Option 3: Command Line
```bash
# Install PlantUML (requires Java)
# On macOS:
brew install plantuml

# On Ubuntu:
sudo apt install plantuml

# Generate PNG from diagram
plantuml system-overview.puml
# Output: system-overview.png
```

### Option 4: IntelliJ IDEA / PyCharm
1. Install the [PlantUML Integration plugin](https://plugins.jetbrains.com/plugin/7017-plantuml-integration)
2. Open any `.puml` file
3. View the diagram in the right panel

## 📋 Diagram Usage Guide

### For New Contributors
**Start with:** `system-overview.puml`
- Understand what each bot does
- See how they connect to external services
- Learn about the shared library

**Then review:** `bot-architecture.puml`
- Dive into component details
- Understand module organization
- See the full dependency graph

### For Bot Developers
**Reference:** `bot-interactions.puml`
- See the required API contracts
- Understand how to call other bots
- Learn about model dependencies

### For Understanding Workflows
**Study:** `data-flow.puml`
- See step-by-step bot execution
- Understand data transformations
- Learn orchestrator coordination patterns

## 🔄 Keeping Diagrams Updated

When making architectural changes:

1. **Adding a new bot:**
   - Update `system-overview.puml` (add bot to main components)
   - Update `bot-architecture.puml` (add bot package and connections)
   - Update `data-flow.puml` (add sequence for new bot)
   - Update `bot-interactions.puml` (add API interfaces)

2. **Adding new shared models:**
   - Update `bot-architecture.puml` (add to Models component)
   - Update `data-flow.puml` (show model usage in sequences)
   - Update `bot-interactions.puml` (add to model dependencies)

3. **Changing bot interactions:**
   - Update `data-flow.puml` (modify sequence flows)
   - Update `bot-interactions.puml` (update invocation patterns)

4. **Adding external integrations:**
   - Update `system-overview.puml` (add to External Services)
   - Update `bot-architecture.puml` (add client components)

## 🎯 Diagram Principles

All diagrams follow these principles:

1. **Clarity over completeness:** Show what matters, hide implementation details
2. **Consistent colors:** Blue for bots, green for shared, orange for data, red for external
3. **Layered views:** Simple overview → detailed architecture → workflow sequences → API contracts
4. **Real code mapping:** Component names match actual files and modules
5. **Annotations:** Include notes explaining key concepts and patterns

## 📖 Related Documentation

- [Architecture Overview](architecture.md) - Written description of the architecture
- [README.md](../README.md) - Project overview and quick start
- [CLAUDE.md](../CLAUDE.md) - AI agent guidance

## 💡 Tips for Creating New Diagrams

If you need to create additional diagrams:

1. **Use consistent styling:**
   ```plantuml
   !theme plain
   skinparam BackgroundColor white
   skinparam roundcorner 10
   ```

2. **Follow the color scheme:**
   - `#4A90E2` - Bots (blue)
   - `#50C878` - Shared library (green)
   - `#FFB84D` - Data/Storage (orange)
   - `#E57373` - External systems (red)

3. **Add helpful notes:**
   - Explain non-obvious relationships
   - Clarify data transformations
   - Document key patterns

4. **Test rendering:**
   - Verify in multiple viewers
   - Check that text is readable
   - Ensure arrows point correctly

5. **Update this README:**
   - Add your diagram to the list
   - Describe what it shows
   - Explain when to use it
