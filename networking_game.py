"""
Networking Game Mode implementation in Python.

This module provides a simple in‑memory game engine that models a
networking challenge system. It is inspired by Khan Academy’s
mastery‑based approach and extends the original networking game with
structured learning modules. Key features include:

* **Daily and weekly tasks** tied to networking activities (e.g. writing
  pitches, connecting with mentors, attending events).
* **Structured modules** that group related tasks, each with its own
  mastery threshold and optional prerequisites. Mastering foundational
  modules unlocks more advanced topics.
* **Optional hints**: Tasks can include optional hints. Users may
  reveal these hints for guidance without any reduction in their
  awarded points.
* **Module progress tracking**: Users accumulate module‑specific points
  toward mastery and can query which modules are available based on
  prerequisites.
* **A streak mechanism** to encourage daily participation.
* **Experience points (XP) and level progression** with named tiers.
* **Badges** that commemorate achievements such as first mentor
  connection, maintaining a long streak, reaching new levels, and
  completing modules.
* **Leaderboards** for comparing user progress.

The code is designed to be easy to extend and integrate into a web or GUI
application (for example, hooking it up to a Figma‑designed interface or
embedding it within a VS Code project). Data persistence is optional and
offered via JSON serialization.

Usage overview:

```
from networking_game import Game, User

# Set up the game and a user
game = Game()
user = game.register_user("alice")

# Assign daily tasks
game.assign_daily_tasks(user)

# User completes a task by its id
task_id = user.tasks[0].id
game.complete_task(user, task_id)

# Check current points, level and badges
print(user.points, user.level.name, [b.name for b in user.badges])

# Save progress to disk
game.save("game_state.json")
```

This module does not enforce any user interface. It simply provides the
underlying logic and data structures needed to build a networking game.

Author: ChatGPT
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import random
from typing import Callable, Dict, List, Optional


@dataclasses.dataclass
class Module:
    """Represents a structured learning module.

    A module groups a set of related tasks together and defines a mastery
    threshold. These modules draw inspiration from Khan Academy’s
    mastery‑based progression: users earn module‑specific points by
    completing associated tasks and work towards a mastery threshold.

    Modules may specify prerequisite modules. A module becomes available
    only after all of its prerequisites have been mastered. This models
    the knowledge tree approach of platforms like Khan Academy, where
    foundational concepts unlock more advanced topics.

    Attributes:
        name: The module's unique name.
        description: A short explanation of what skills this module covers.
        task_templates: A list of template dictionaries, each containing
            at least a `description` and `points`, and optionally a `hint`.
        mastery_threshold: The total points required in this module to achieve
            mastery.
        prerequisites: A list of module names that must be mastered
            before this module becomes available. Defaults to an empty list.
    """
    name: str
    description: str
    task_templates: List[Dict]
    mastery_threshold: int
    prerequisites: List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Task:
    """Represents a task or challenge within the networking game.

    Tasks may belong to daily, weekly or module categories. Module tasks
    contribute towards mastery of a specific learning module. Each task can
    optionally include a hint to guide the user; hints are inspired by the
    pedagogical approach of Khan Academy.

    Attributes:
        id: A unique identifier for the task.
        description: A human‑readable description of what the task requires.
        points: The number of experience points awarded upon completion.
        category: "daily", "weekly" or "module". This informs streak handling
            and scheduling logic.
        module_name: If the category is "module", the name of the associated
            module; otherwise None.
        hint: Optional hint text to assist the user. Hints may reduce points
            when used, depending on the game design (not enforced here).
        completed: A flag indicating whether the task has been completed.
        due_date: The deadline for the task. For daily tasks this is typically
            the end of the current day; for weekly tasks it's the end of the
            current week; module tasks may not have a due date and can remain
            open until mastered.
        hint_used: Whether the hint has been revealed by the user.
    """
    id: str
    description: str
    points: int
    category: str
    module_name: Optional[str] = None
    hint: Optional[str] = None
    completed: bool = False
    due_date: Optional[datetime.date] = None
    hint_used: bool = False

    def is_overdue(self, today: Optional[datetime.date] = None) -> bool:
        """Return True if the task is past its due date and not completed."""
        today = today or datetime.date.today()
        return not self.completed and self.due_date is not None and today > self.due_date

    def use_hint(self) -> Optional[str]:
        """Reveal the hint and mark it as used.

        The hint can only be used once. Hints do not automatically alter
        points; any point adjustments should be implemented in the game logic
        if desired.

        Returns:
            The hint text if available and not yet used; otherwise None.
        """
        if self.hint and not self.hint_used:
            self.hint_used = True
            return self.hint
        return None


@dataclasses.dataclass
class Badge:
    """Represents an achievement badge awarded when a condition is met.

    Attributes:
        id: A unique identifier.
        name: A human‑friendly name.
        description: Explanation of why the badge was awarded.
        condition: A callable taking a User and returning True if the badge
            criteria are satisfied.
    """
    id: str
    name: str
    description: str
    condition: Callable[["User"], bool]


@dataclasses.dataclass
class Level:
    """Represents a progression tier based on accumulated points.

    Attributes:
        name: The label for the level (e.g. "Rookie Connector").
        min_points: The minimum cumulative points required to reach this level.
        max_points: The inclusive maximum points for this level. Use None for
            the highest tier.
    """
    name: str
    min_points: int
    max_points: Optional[int]


class User:
    """Represents a player participating in the networking game.

    Users accumulate points, track streaks, earn badges and levels, and
    maintain a list of assigned tasks. This class encapsulates all
    progress‑related data for a single player.
    """

    def __init__(self, username: str):
        self.username: str = username
        self.points: int = 0
        self.level: Level = Game.LEVELS[0]
        self.badges: List[Badge] = []
        self.tasks: List[Task] = []
        self.streak: int = 0
        self.last_active: Optional[datetime.date] = None
        # Track progress towards each module's mastery. Keys are module names,
        # values are accumulated points within that module.
        self.module_points: Dict[str, int] = {}

    def to_dict(self) -> Dict:
        """Serialize the user to a JSON‑serializable dictionary."""
        return {
            "username": self.username,
            "points": self.points,
            "level": self.level.name,
            "badges": [badge.id for badge in self.badges],
            "streak": self.streak,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "tasks": [dataclasses.asdict(task) for task in self.tasks],
            "module_points": self.module_points,
        }

    @classmethod
    def from_dict(cls, data: Dict, level_lookup: Dict[str, Level], badge_lookup: Dict[str, Badge]) -> "User":
        """Deserialize a user from a dictionary.

        Args:
            data: The dictionary produced by `to_dict()`.
            level_lookup: A mapping from level names to Level objects.
            badge_lookup: A mapping from badge ids to Badge objects.

        Returns:
            A reconstructed User instance.
        """
        user = cls(data["username"])
        user.points = data.get("points", 0)
        level_name = data.get("level")
        user.level = level_lookup[level_name]
        user.badges = [badge_lookup[bid] for bid in data.get("badges", [])]
        user.streak = data.get("streak", 0)
        last_active_str = data.get("last_active")
        if last_active_str:
            user.last_active = datetime.date.fromisoformat(last_active_str)
        # Reconstruct tasks
        user.tasks = []
        for tdata in data.get("tasks", []):
            task = Task(**{
                "id": tdata["id"],
                "description": tdata["description"],
                "points": tdata["points"],
                "category": tdata["category"],
                "module_name": tdata.get("module_name"),
                "hint": tdata.get("hint"),
                "completed": tdata.get("completed", False),
                "due_date": datetime.date.fromisoformat(tdata["due_date"]) if tdata.get("due_date") else None,
                "hint_used": tdata.get("hint_used", False),
            })
            user.tasks.append(task)
        # Restore module points
        user.module_points = data.get("module_points", {})
        return user


class Game:
    """Manages users, tasks, levels and badges for the networking game.

    This class stores the global definitions for levels and badges, and provides
    methods to register users, generate tasks, update progress and persist
    state.
    """

    # Define progression tiers. Adjust the thresholds and names as desired.
    LEVELS: List[Level] = [
        Level(name="Rookie Connector", min_points=0, max_points=20),
        Level(name="Engaged Networker", min_points=21, max_points=50),
        Level(name="Community Builder", min_points=51, max_points=80),
        Level(name="Industry Insider", min_points=81, max_points=None),
    ]

    # Predefine badges. The conditions are specified as callables.
    BADGES: List[Badge] = []  # This will be populated in __init__.

    def __init__(self):
        # Populate badge conditions. Many conditions reference game state, so
        # they are defined lazily here rather than as class constants.
        self.badge_lookup: Dict[str, Badge] = {}
        self._register_badges()
        # Lookup for quick level retrieval by name
        self.level_lookup: Dict[str, Level] = {lvl.name: lvl for lvl in Game.LEVELS}
        # In‑memory user registry
        self.users: Dict[str, User] = {}

        # Predefined task templates. These represent categories of tasks that
        # will be instantiated fresh for each assignment.
        self.daily_task_templates: List[Dict] = [
            {"description": "Write a 30‑second elevator pitch using the chat coach.", "points": 5},
            {"description": "Send a personalized intro message to a mentor or peer.", "points": 5},
            {"description": "Review a recommended article and post one insight.", "points": 4},
            {"description": "Connect with two alumni or classmates in your field.", "points": 6},
        ]
        self.weekly_task_templates: List[Dict] = [
            {"description": "Attend a recommended networking event and share a takeaway.", "points": 12},
            {"description": "Complete a mock coffee chat session in Practice Mode.", "points": 10},
            {"description": "Enroll in a mini‑course from the resource recommender.", "points": 8},
        ]

        # Define learning modules inspired by Khan Academy. Each module groups
        # related tasks and specifies a mastery threshold. When a user
        # accumulates enough points in a module, it can be considered
        # completed. Additional modules can be added here as the game grows.
        self.modules: Dict[str, Module] = {
            "Profile Optimization": Module(
                name="Profile Optimization",
                description="Craft a compelling LinkedIn profile that highlights your strengths and goals.",
                task_templates=[
                    {"description": "Update your LinkedIn headline with targeted keywords.", "points": 5, "hint": "Highlight your core skills and aspirations."},
                    {"description": "Add at least three relevant skills to your profile.", "points": 4, "hint": "Research skills valued in your desired roles."},
                    {"description": "Write a compelling summary that tells your story.", "points": 5, "hint": "Share your career goals and personal narrative."},
                ],
                mastery_threshold=12,
                prerequisites=[],
            ),
            "Pitch Mastery": Module(
                name="Pitch Mastery",
                description="Develop and refine your elevator pitch to confidently introduce yourself.",
                task_templates=[
                    {"description": "Write a 30‑second elevator pitch using the chat coach.", "points": 5, "hint": "Focus on who you are, what you do and your aspirations."},
                    {"description": "Record your pitch and evaluate its clarity.", "points": 5, "hint": "Practice speaking with a timer and watch your pace."},
                    {"description": "Polish your pitch and integrate a personal story.", "points": 6, "hint": "Add a memorable hook that shows your passion."},
                ],
                mastery_threshold=14,
                prerequisites=["Profile Optimization"],
            ),
            "Mentor Outreach": Module(
                name="Mentor Outreach",
                description="Learn how to identify and approach mentors effectively.",
                task_templates=[
                    {"description": "Identify a potential mentor's profile and note common interests.", "points": 4, "hint": "Look for shared experiences or values."},
                    {"description": "Draft a personalized outreach message to a potential mentor.", "points": 5, "hint": "Mention shared interests and what you hope to learn."},
                    {"description": "Send your message and log the response.", "points": 6, "hint": "Follow up politely and thank them for their time."},
                ],
                mastery_threshold=12,
                prerequisites=["Profile Optimization", "Pitch Mastery"],
            ),
            "Event Participation": Module(
                name="Event Participation",
                description="Engage meaningfully with networking events and follow up afterwards.",
                task_templates=[
                    {"description": "Find a networking event using the event finder.", "points": 4, "hint": "Search for events that align with your goals and schedule."},
                    {"description": "Attend the event and make two new connections.", "points": 6, "hint": "Prepare icebreakers and focus on listening."},
                    {"description": "Send follow‑up messages to your new connections.", "points": 5, "hint": "Reference your conversation and express interest in staying in touch."},
                ],
                mastery_threshold=12,
                prerequisites=["Profile Optimization", "Pitch Mastery"],
            ),
            "Resource Integration": Module(
                name="Resource Integration",
                description="Integrate learning resources into your professional growth.",
                task_templates=[
                    {"description": "Read a recommended article and summarise key takeaways.", "points": 4, "hint": "Note the main arguments and how they apply to your career."},
                    {"description": "Enroll in a short course and share your reflections.", "points": 6, "hint": "Focus on actionable insights and new skills."},
                    {"description": "Write a post or journal entry about what you learned.", "points": 5, "hint": "Connect the material to your personal goals and experiences."},
                ],
                mastery_threshold=12,
                prerequisites=["Profile Optimization"],
            ),
        }

        # After defining modules, create badges that mark module mastery. These
        # badges are registered dynamically based on the modules defined
        # above. This must happen after modules are set up so that
        # badge conditions can reference the mastery thresholds.
        self._register_module_badges()

    def _register_badges(self) -> None:
        """Define the available badges and their conditions."""
        # Clear existing list in case of re‑initialization
        Game.BADGES.clear()
        # Badge for completing the first connection
        def first_connection(user: User) -> bool:
            return user.points >= 5  # Enough points for one small task
        Game.BADGES.append(Badge(
            id="badge_first_connection",
            name="First Connection",
            description="Complete your first networking task.",
            condition=first_connection,
        ))
        # Badge for maintaining a 7‑day streak
        def seven_day_streak(user: User) -> bool:
            return user.streak >= 7
        Game.BADGES.append(Badge(
            id="badge_7_day_streak",
            name="Consistency Star",
            description="Maintain a 7‑day streak of daily activity.",
            condition=seven_day_streak,
        ))
        # Badge for reaching the Engaged Networker level
        def engaged_networker(user: User) -> bool:
            return user.level.name == "Engaged Networker"
        Game.BADGES.append(Badge(
            id="badge_engaged",
            name="Engaged Networker",
            description="Reach the Engaged Networker level.",
            condition=engaged_networker,
        ))
        # Badge for reaching Industry Insider level
        def industry_insider(user: User) -> bool:
            return user.level.name == "Industry Insider"
        Game.BADGES.append(Badge(
            id="badge_industry",
            name="Industry Insider",
            description="Achieve the highest level in the networking game.",
            condition=industry_insider,
        ))
        # Populate lookup for quick retrieval
        self.badge_lookup = {badge.id: badge for badge in Game.BADGES}

    def _register_module_badges(self) -> None:
        """Generate badges for completing each module.

        For every defined module, create a badge that is awarded when the
        user accumulates points equal to or exceeding the module's
        mastery_threshold. These badges are added to the global BADGES list
        and the badge lookup.
        """
        for module in self.modules.values():
            badge_id = f"badge_module_{module.name.replace(' ', '_').lower()}"
            badge_name = f"{module.name} Master"
            badge_desc = f"Achieve mastery in the {module.name} module."
            def condition_factory(mod: Module) -> Callable[[User], bool]:
                return lambda user: user.module_points.get(mod.name, 0) >= mod.mastery_threshold
            badge = Badge(
                id=badge_id,
                name=badge_name,
                description=badge_desc,
                condition=condition_factory(module),
            )
            Game.BADGES.append(badge)
        # Refresh badge lookup now that module badges have been added
        self.badge_lookup = {badge.id: badge for badge in Game.BADGES}

    def register_user(self, username: str) -> User:
        """Register a new user and return the user instance.

        If a user with the given username already exists, the existing user
        instance is returned. Usernames are treated case‑sensitively.
        """
        if username in self.users:
            return self.users[username]
        user = User(username)
        self.users[username] = user
        return user

    def assign_daily_tasks(self, user: User, num_tasks: int = 2) -> None:
        """Assign daily tasks to the user.

        Tasks are drawn randomly from the daily_task_templates. Existing
        incomplete daily tasks are carried over until their due date passes or
        they are completed.

        Args:
            user: The user to assign tasks to.
            num_tasks: The number of fresh tasks to assign.
        """
        today = datetime.date.today()
        # Remove expired tasks
        user.tasks = [t for t in user.tasks if not t.is_overdue(today)]
        # Count how many daily tasks are still pending
        pending_daily = [t for t in user.tasks if t.category == "daily"]
        # Assign new tasks until the desired number is reached
        while len(pending_daily) < num_tasks:
            template = random.choice(self.daily_task_templates)
            task_id = f"d{int(datetime.datetime.now().timestamp() * 1000)}{random.randint(0, 999)}"
            due = today  # daily tasks are due by end of day
            new_task = Task(
                id=task_id,
                description=template["description"],
                points=template["points"],
                category="daily",
                due_date=due,
            )
            user.tasks.append(new_task)
            pending_daily.append(new_task)

    def assign_weekly_tasks(self, user: User, num_tasks: int = 1) -> None:
        """Assign weekly tasks to the user.

        Weekly tasks are assigned once per week and are due by the end of the
        current ISO week (Monday=1, Sunday=7). Existing weekly tasks are
        retained until completed or expired.
        """
        today = datetime.date.today()
        year, week_num, dow = today.isocalendar()
        # Compute end of the current week (Sunday)
        end_of_week = today + datetime.timedelta(days=(7 - dow))
        # Remove expired tasks
        user.tasks = [t for t in user.tasks if not t.is_overdue(today)]
        # Count existing weekly tasks
        pending_weekly = [t for t in user.tasks if t.category == "weekly"]
        while len(pending_weekly) < num_tasks:
            template = random.choice(self.weekly_task_templates)
            task_id = f"w{int(datetime.datetime.now().timestamp() * 1000)}{random.randint(0, 999)}"
            new_task = Task(
                id=task_id,
                description=template["description"],
                points=template["points"],
                category="weekly",
                due_date=end_of_week,
            )
            user.tasks.append(new_task)
            pending_weekly.append(new_task)

    def assign_module_tasks(self, user: User, module_name: str, num_tasks: int = 2) -> None:
        """Assign tasks from a specified module to the user.

        This method assigns up to `num_tasks` new tasks from the given module.
        Existing incomplete tasks for this module are retained. If the user has
        already mastered the module (i.e. accumulated points >= mastery threshold),
        no new tasks are assigned.

        Args:
            user: The user to assign tasks to.
            module_name: The name of the module from which tasks should be drawn.
            num_tasks: The maximum number of new tasks to assign.
        """
        # Ensure module exists
        module = self.modules.get(module_name)
        if not module:
            raise ValueError(f"Unknown module: {module_name}")
        # Check prerequisites: user must have mastered all prerequisites
        for prereq in module.prerequisites:
            prereq_points = user.module_points.get(prereq, 0)
            prereq_mod = self.modules.get(prereq)
            # If prerequisite module definition missing, treat as incomplete
            if not prereq_mod or prereq_points < prereq_mod.mastery_threshold:
                # Do not assign tasks if prerequisites not met
                return
        # Check if module already mastered
        current_points = user.module_points.get(module_name, 0)
        if current_points >= module.mastery_threshold:
            return  # Already completed
        # Remove expired tasks and retain incomplete ones
        today = datetime.date.today()
        user.tasks = [t for t in user.tasks if not t.is_overdue(today)]
        # Find existing module tasks
        pending_module = [t for t in user.tasks if t.category == "module" and t.module_name == module_name]
        while len(pending_module) < num_tasks:
            template = random.choice(module.task_templates)
            task_id = f"m{int(datetime.datetime.now().timestamp() * 1000)}{random.randint(0, 999)}"
            new_task = Task(
                id=task_id,
                description=template["description"],
                points=template["points"],
                category="module",
                module_name=module_name,
                hint=template.get("hint"),
                due_date=None,
            )
            user.tasks.append(new_task)
            pending_module.append(new_task)

    def get_module_progress(self, user: User) -> Dict[str, float]:
        """Return the progress for each module as a fraction between 0 and 1.

        The progress value represents the ratio of points the user has
        accumulated in a module to the module's mastery threshold. Values are
        capped at 1.0 to represent completion. Modules with no progress
        return 0.0.

        Args:
            user: The user whose progress should be computed.

        Returns:
            A dictionary mapping module names to progress values.
        """
        progress: Dict[str, float] = {}
        for name, module in self.modules.items():
            points = user.module_points.get(name, 0)
            fraction = points / module.mastery_threshold if module.mastery_threshold else 0.0
            progress[name] = min(1.0, fraction)
        return progress

    def get_available_modules(self, user: User) -> List[str]:
        """Return a list of module names that the user can currently access.

        A module is available if the user has mastered all of its
        prerequisites. Modules with no prerequisites are always available.

        Args:
            user: The user whose available modules are being queried.

        Returns:
            A list of module names sorted in arbitrary order.
        """
        available: List[str] = []
        for name, module in self.modules.items():
            # Check if module is already mastered; still include so user can revisit tasks
            prerequisites_met = True
            for prereq in module.prerequisites:
                prereq_mod = self.modules.get(prereq)
                if not prereq_mod:
                    prerequisites_met = False
                    break
                if user.module_points.get(prereq, 0) < prereq_mod.mastery_threshold:
                    prerequisites_met = False
                    break
            if prerequisites_met:
                available.append(name)
        return available

    def use_task_hint(self, user: User, task_id: str) -> Optional[str]:
        """Reveal the hint for a given task and mark it as used.

        Using a hint does not immediately alter the user's points, but
        completion of the task will apply a points penalty. If no hint is
        available or the task is already completed, returns None.

        Args:
            user: The user requesting the hint.
            task_id: The identifier of the task for which the hint is requested.

        Returns:
            The hint text if available; otherwise None.
        """
        for task in user.tasks:
            if task.id == task_id and not task.completed:
                return task.use_hint()
        return None

    def complete_task(self, user: User, task_id: str) -> bool:
        """Mark a task as completed and update user progress.

        Args:
            user: The user completing the task.
            task_id: The identifier of the task to complete.

        Returns:
            True if the task was found and completed, False otherwise.
        """
        today = datetime.date.today()
        # Find the task
        for task in user.tasks:
            if task.id == task_id and not task.completed:
                # Mark completed and award points
                task.completed = True
                # Award full points regardless of hint usage. Hints
                # provide guidance but do not reduce the points earned.
                awarded = task.points
                user.points += awarded
                # If this task belongs to a module, accumulate full module points
                if task.category == "module" and task.module_name:
                    current = user.module_points.get(task.module_name, 0)
                    user.module_points[task.module_name] = current + awarded
                # Update streak: increment if last active was yesterday or today
                if user.last_active is None or (today - user.last_active).days <= 1:
                    user.streak += 1
                else:
                    user.streak = 1
                user.last_active = today
                # Update level and badges
                self._update_level(user)
                self._update_badges(user)
                return True
        return False

    def _update_level(self, user: User) -> None:
        """Update the user's level based on current point totals."""
        # Find the highest level that meets the user's point total
        for level in reversed(Game.LEVELS):
            if level.max_points is None:
                # Open‑ended highest level
                if user.points >= level.min_points:
                    user.level = level
                    return
            else:
                if level.min_points <= user.points <= level.max_points:
                    user.level = level
                    return

    def _update_badges(self, user: User) -> None:
        """Check for new badges and award them as appropriate."""
        for badge in Game.BADGES:
            if badge not in user.badges and badge.condition(user):
                user.badges.append(badge)

    def get_leaderboard(self, top_n: int = 10) -> List[Dict[str, object]]:
        """Return a sorted leaderboard of users based on points and streaks.

        Users are ranked primarily by points, then by streak length, and then
        alphabetically by username for deterministic ordering. Only the top
        `top_n` entries are returned by default.
        """
        sorted_users = sorted(
            self.users.values(),
            key=lambda u: (-u.points, -u.streak, u.username),
        )
        leaderboard = []
        for user in sorted_users[:top_n]:
            leaderboard.append({
                "username": user.username,
                "points": user.points,
                "level": user.level.name,
                "streak": user.streak,
                "badges": [b.name for b in user.badges],
            })
        return leaderboard

    def save(self, filepath: str) -> None:
        """Serialize the game state to a JSON file."""
        data = {
            "users": {username: user.to_dict() for username, user in self.users.items()},
            "timestamp": datetime.datetime.now().isoformat(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load(self, filepath: str) -> None:
        """Load game state from a JSON file, replacing any existing users."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        users_data = data.get("users", {})
        self.users = {}
        for username, udata in users_data.items():
            user = User.from_dict(udata, level_lookup=self.level_lookup, badge_lookup=self.badge_lookup)
            self.users[username] = user
