from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Date
from sqlalchemy.orm import relationship, backref
from database import Base
from werkzeug.security import generate_password_hash, check_password_hash

COMMON_STATUS_OPTIONS = ['Open', 'Closed', 'On-Hold']
CHANGE_STATUS_OPTIONS = COMMON_STATUS_OPTIONS + ['Approved', 'Rejected']
DAD_STATUS_OPTIONS = ['Raised', 'Approved', 'Rejected']
PROJECT_STATUS_OPTIONS = ['Active', 'On-Hold', 'Closed', 'Cancelled']

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    is_admin = Column(Boolean, default=False)

    help_text = {
        "username": "Enter a unique username for this account.",
        "password_hash": "Enter a strong password containing letters and numbers.",
        "is_admin": "Grant full administrative privileges to this user?"
    }

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Project(Base):
    __tablename__ = "projects"
    status_options = PROJECT_STATUS_OPTIONS
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    status = Column(String(50), default='Active')

    help_text = {
        "name": "Enter the official name of the project.",
        "status": "Current state of the project (e.g., Active, On Hold, Closed)."
    }

    # Relationships
    changes = relationship('ChangeLog', back_populates='project', cascade="all, delete-orphan")
    actions = relationship('ActionsLog', back_populates='project', cascade="all, delete-orphan")
    risks = relationship('RiskLog', back_populates='project', cascade="all, delete-orphan")
    issues = relationship('IssuesLog', back_populates='project', cascade="all, delete-orphan")
    dads = relationship('DADLog', back_populates='project', cascade="all, delete-orphan")
    tasks = relationship('ProjectTask', back_populates='project', cascade="all, delete-orphan")

class ChangeLog(Base):
    __tablename__ = "change_logs"
    type_options = ['Constraint', 'Change']
    status_options = CHANGE_STATUS_OPTIONS

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates='changes')
    
    type = Column(String(50))
    title = Column(String(200))
    description = Column(Text)
    scope_impact = Column(Boolean)
    schedule_impact = Column(Boolean)
    cost_impact = Column(Boolean)
    status = Column(String(50))
    submitted_by = Column(String(100))
    approved_by = Column(String(100))
    date_received = Column(Date)

    help_text = {
        "type": "Is this a request to change the plan or a limiting constraint?",
        "title": "A short, descriptive headline for this change.",
        "description": "Provide full details on what is changing and why.",
        "scope_impact": "Does this change affect the project deliverables?",
        "schedule_impact": "Will this change delay the timeline?",
        "cost_impact": "Will this change require additional budget?",
        "status": "Current approval status of this request.",
        "submitted_by": "Name of the person requesting this change.",
        "approved_by": "Name of the stakeholder who approved this change.",
        "date_received": "Date the request was formally received."
    }

class ActionsLog(Base):
    __tablename__ = "actions_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates='actions')
    
    description = Column(Text)
    status = Column(String(50))
    dependency = Column(String(100))
    workstream = Column(String(100))
    date_raised = Column(Date)
    target_end_date = Column(Date)
    actual_closure_date = Column(Date)
    owner = Column(String(100))
    notes = Column(Text)

    help_text = {
        "description": "Describe the specific action required.",
        "status": "Current status of this action item.",
        "dependency": "List any other tasks or items this action is waiting on.",
        "workstream": "Which department or team is responsible for this?",
        "date_raised": "Date this action was identified.",
        "target_end_date": "When must this action be completed by?",
        "actual_closure_date": "Date the action was actually completed.",
        "owner": "Person responsible for completing this action.",
        "notes": "Any additional context or progress updates."
    }

class RiskLog(Base):
    __tablename__ = "risk_logs"
    type_options = ['Internal', 'External']
    probability_options = ['High', 'Medium', 'Low']
    impact_options = ['High', 'Medium', 'Low']
    response_strategy_options = ['Mitigation', 'Contingency', 'Transference', 'Avoidance', 'Acceptance']
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates='risks')
    
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(50))
    type = Column(String(50))
    workstream = Column(String(100))
    probability = Column(String(50))
    impact = Column(String(50))
    rag = Column(String(20))
    date_raised = Column(Date)
    raised_by = Column(String(100))
    response_strategy = Column(String(100))
    response_action = Column(Text)
    action_owner = Column(String(100))
    notes = Column(Text)

    help_text = {
        "title": "Short name for this risk.",
        "description": "Describe what might happen and the potential consequences.",
        "status": "Is this risk currently active?",
        "type": "Does this risk originate from inside or outside the organization?",
        "workstream": "The specific area of work affected by this risk.",
        "probability": "How likely is this risk to occur?",
        "impact": "How severe would the consequences be?",
        "rag": "Overall status color (Red = Critical, Green = Controlled).",
        "response_strategy": "How do you intend to handle this risk?\n\n - Mitigation: Early action to remove/reduce\n - Contingency: Some impact within tolerances\n - Planned actions if risk occurs\n - Transference: Insurance/penalty clauses\n - Avoidance: Eliminate risk by changing project\n - Acceptance: Tolerate risk",
        "response_action": "Specific steps taken to execute the chosen strategy.",
        "action_owner": "Person responsible for managing this risk.",
        "date_raised": "Date this risk was identified.",
        "raised_by": "Who raised this item?"
    }

class IssuesLog(Base):
    __tablename__ = "issues_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates='issues')
    
    title = Column(String(200))
    description = Column(Text)
    rag = Column(String(20))
    status = Column(String(50))
    workstream = Column(String(100))
    date_raised = Column(Date)
    remediation_action = Column(Text)
    action_owner = Column(String(100))
    target_closure_date = Column(Date)
    actual_closure_date = Column(Date)
    notes = Column(Text)

    help_text = {
        "title": "Headline summarizing the issue.",
        "description": "Detailed explanation of the problem currently occurring.",
        "rag": "Severity level of the issue.",
        "status": "Current status of the issue.",
        "workstream": "The team or department facing this issue.",
        "remediation_action": "What steps are being taken to fix this?",
        "action_owner": "Person assigned to resolve this issue.",
        "date_raised": "Date the issue was first reported.",
        "target_closure_date": "Expected date for resolution.",
        "actual_closure_date": "Date the issue was resolved.",
        "notes": "Updates or additional details on the issue."
    }

class DADLog(Base):
    __tablename__ = "dad_logs"
    type_options = ['Dependency', 'Assumption', 'Decision']
    status_options = DAD_STATUS_OPTIONS

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates='dads')
    
    description = Column(Text)
    type = Column(String(50))
    plan_version = Column(String(50))
    impact = Column(String(50))
    status = Column(String(50))
    workstream = Column(String(100))
    date_raised = Column(Date)
    raised_by = Column(String(100))
    date_agreed = Column(Date)
    agreed_by = Column(String(100))
    notes = Column(Text)

    help_text = {
        "type": "Classify this item.",
        "description": "Describe the dependency, assumption, or decision details.",
        "plan_version": "Which version of the project plan does this relate to?",
        "impact": "Describe the effect this has on the project.",
        "status": "Current status (e.g., Raised, Approved, Rejected).",
        "workstream": "Related workstream.",
        "date_raised": "Date this item was logged.",
        "raised_by": "Who raised this item?",
        "date_agreed": "Date the decision was finalized or assumption validated.",
        "agreed_by": "Who validated or authorized this item?",
        "notes": "Additional context."
    }

class ProjectTask(Base):
    __tablename__ = "project_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', back_populates='tasks')
    
    parent_id = Column(Integer, ForeignKey('project_tasks.id'), nullable=True)
    children = relationship('ProjectTask', backref=backref('parent', remote_side=[id]), cascade="all, delete-orphan")
    
    task_id = Column(String(50)) # User facing ID
    task_name = Column(String(200))
    resource = Column(String(100))
    workstream = Column(String(100))
    start_date = Column(Date)
    end_date = Column(Date)
    completion = Column(Integer) # 0-100

    help_text = {
        "task_id": "Display ID for the task \n(e.g., TASK1 TASK1.2 TASK1.2.1).\nCan be left as is and system will autogenerate.",
        "task_name": "Name of the task.",
        "parent_id": "ID of parent task if this is a sub-task.",
        "resource": "Resource assigned to perform this task.",
        "workstream": "Category or team this task belongs to.",
        "start_date": "Planned start date.",
        "end_date": "Planned completion date.",
        "completion": "Current progress percentage (0-100)."
    }
