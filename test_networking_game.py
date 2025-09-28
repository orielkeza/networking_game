import sys
sys.path.append('/home/oai/share')
from networking_game import Game

def run_test():
    game = Game()
    user = game.register_user('alice')
    # Assign tasks
    game.assign_daily_tasks(user)
    game.assign_weekly_tasks(user)
    # Determine available modules (should include Profile Optimization only at start)
    available = game.get_available_modules(user)
    print('Available modules at start:', available)
    # Assign tasks from Profile Optimization module
    if 'Profile Optimization' in available:
        game.assign_module_tasks(user, 'Profile Optimization')
        module_tasks = [t for t in user.tasks if t.category == 'module']
        print('Module tasks:', [(t.description, t.module_name) for t in module_tasks])
        # Use hint on the first module task
        if module_tasks:
            hint = game.use_task_hint(user, module_tasks[0].id)
            print('Hint provided:', hint)
            # Complete the task
            game.complete_task(user, module_tasks[0].id)
            print('Points after completing first module task:', user.points)
            print('Module points:', user.module_points)
            print('Module progress:', game.get_module_progress(user))
            print('User level:', user.level.name)

if __name__ == '__main__':
    run_test()
