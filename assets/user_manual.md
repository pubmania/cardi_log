# CARDI Log User Manual

Welcome to **CARDI Log**, your comprehensive tool for managing project logs and plans. This manual guides you through the application's features and navigation.



## Getting Started
**Login**: Enter your credentials to access the application. The default admin account is `admin` with password `password123`.
**Dashboard**: Upon login, you see the Dashboard, providing a high-level overview of your projects and recent activities.

## Navigation
Use the **Sidebar** on the left to navigate between different views:
- **Dashboard**: Home screen.
- **Projects**: Manage your portfolio of projects.
- **Project Plan**: Gantt charts and task lists.
- **Logs**: Risks, Issues, Actions, DADs, Changes.

Use the **Top Bar** for:
- **Theme Toggle**: Switch between Light and Dark mode.
- **Refresh**: Reload the current view.
- **Profile Menu**: Access Settings, Help, About, User Management (Admin only), and Logout.

## Projects
The **Projects** view lists all your active projects.
- **Add Project**: Click the `+` button in the top right.
- **Edit/Delete**: Use the icons in the Actions column.
- **Select Project**: Click a project name or use the dropdown in any Log view to filter data for that project.

## Project Plan
Manage your project schedule here.
- **Views**: Switch between **Gantt Chart** and **Task List** using the tabs.
- **Gantt Chart**: Visual timeline of tasks. Use the "Scale" dropdown to change granularity (Days, Weeks, etc.).
- **Task List**: Tabular view of all tasks.
    - **Add Task**: Click `Add Task` to create a new task.
    - **Sub-Tasks**: Click the `Playlist Add` icon on a task to add a sub-task.
- **Import/Export**: Use buttons to upload tasks from CSV or download current tasks.

## Logs (CARDI)
Each log tracks specific project items. All logs share common features:
- **Filter**: Click the Filter icon to search/filter items.
- **Columns**: Click the Columns icon to show/hide specific data fields.
- **Help Icons**: Click the `?` icon next to any field title for a description of that field.

### Risk Log
Tracks potential future events that could impact objectives.
- **RAG**: Red/Amber/Green status.
- **Impact/Probability**: Assess the severity and likelihood.

### Issue Log
Tracks current problems that are already impacting the project.
- **Status**: Open, Closed, etc.
- **Remediation**: Steps being taken to fix the issue.

### Action Log
Tracks tasks and to-dos assigned to individuals.
- **Owner**: Who is responsible.
- **Due Date**: When it must be completed.

### DAD Log
**Decisions, Assumptions, and Dependencies**.
- **Type**: Categorize items as Decision, Assumption, or Dependency.

### Change Log
Tracks formal requests for constraints / changes to scope, budget, or timeline.
- **Approval Status**: Approved, Rejected, Pending.
- **Cost Impact**: Financial effect of the change.

## Settings
Access via the Profile Menu -> **Settings**.
- **Theme Mode**: toggle light/dark.
- **Color Theme**: Choose the primary accent color.
- **Heading Color**: Customize the color of page titles and help icons.

## Admin
(Visible only to Administrators)
- **User Management**: Add, edit, or delete users.
- **Password Reset**: Reset passwords for other users.
