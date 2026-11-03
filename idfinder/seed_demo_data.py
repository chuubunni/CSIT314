"""Command-line wrapper around idfinder/demo_seed.py (optional: only for demos and presentations).

    flask --app idfinder init-db          # only if you want a clean database (erases existing data!)
    python seed_demo_data.py              # add demo data (does nothing if it is already there)
    python seed_demo_data.py --clean      # remove only the demo rows
    python seed_demo_data.py --db instance/idfinder.sqlite --days 120
    python seed_demo_data.py --extend         # add 137 more designers, 45 customers and 200 projects (with pictures)
    python seed_demo_data.py --use-existing   # keep the designers/projects/pictures already in the database
                                              # and add customers, views, jobs and reviews on top (use a COPY)

Demo manager login: manager@demo.test / Demo1234!
"""
import argparse
import os

from idfinder.demo_seed import DemoSeeder


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--clean', action='store_true', help='remove the demo rows instead of adding them')
    p.add_argument('--db', default=os.path.join('instance', 'idfinder.sqlite'), help='SQLite file to use')
    p.add_argument('--days', type=int, default=90, help='spread the activity over this many days')
    p.add_argument('--scale', type=float, default=1.0, help='multiply the amount of activity (e.g. 0.5 or 2)')
    p.add_argument('--use-existing', action='store_true', help='build on the designers and projects already in the database')
    p.add_argument('--extend', action='store_true', help='add more designers, customers and projects to a database that already has demo data')
    p.add_argument('--new-designers', type=int, default=137)
    p.add_argument('--new-customers', type=int, default=45)
    p.add_argument('--new-projects', type=int, default=200)
    a = p.parse_args()
    if a.extend:
        from idfinder.demo_extend import extend
        print(extend(a.db, a.new_designers, a.new_customers, a.new_projects, a.days) or 'The extra demo data is already there.')
        return
    seeder = DemoSeeder(a.db, days=a.days, scale=a.scale, use_existing=a.use_existing)
    if a.clean:
        print(f'Removed {seeder.clean()} demo users (and their projects, views, favourites, jobs and reviews).')
    else:
        print(seeder.seed() or 'Demo data is already there. Run with --clean first to regenerate it.')


if __name__ == '__main__':
    main()
