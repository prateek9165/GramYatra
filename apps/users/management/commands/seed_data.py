"""
GramYatra — Seed Management Command
Usage: python manage.py seed_data

Populates:
  - 4 sample users (one per role)
  - 5 cell towers
  - 2 routes with stops
  - 4 vehicles
  - Schedules
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.conf import settings


class Command(BaseCommand):
    help = 'Seed GramYatra database with sample data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('🌱 Seeding GramYatra database...'))

        self._create_users()
        self._create_cell_towers()
        self._create_routes()
        self._create_vehicles()
        self._create_schedules()

        self.stdout.write(self.style.SUCCESS('\n✅ Seeding complete! Check /admin for all data.'))

    # ── Users ─────────────────────────────────────────────
    def _create_users(self):
        from apps.users.models import User, DriverProfile, OwnerProfile

        users_data = [
            {'phone': '9876543210', 'name': 'Ramesh Kumar',    'role': 'consumer'},
            {'phone': '8765432109', 'name': 'Mahesh Singh',    'role': 'driver'},
            {'phone': '7654321098', 'name': 'Suresh Transport','role': 'owner'},
            {'phone': '6543210987', 'name': 'AK Sharma RTO',   'role': 'rto'},
        ]

        for ud in users_data:
            user, created = User.objects.get_or_create(
                phone=ud['phone'],
                defaults={'name': ud['name'], 'role': ud['role'],
                          'is_active': True, 'is_verified': True}
            )
            user.set_password('GramYatra@123')

            if ud['role'] == 'rto':
                user.rto_passkey_hash = make_password(settings.RTO_PASSKEY)

            user.save()

            if ud['role'] == 'driver' and created:
                DriverProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'license_number': 'MP04/DL/2019/1234',
                        'is_rto_verified': True,
                        'is_on_duty': True,
                        'total_trips': 1847,
                        'rating': 4.8,
                    }
                )
            elif ud['role'] == 'owner' and created:
                OwnerProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'company_name': 'Suresh Transport Co.',
                        'is_rto_verified': True,
                    }
                )

            status = '✅ created' if created else '⏭  exists'
            self.stdout.write(f'  {status}: {ud["role"]} — {ud["name"]} ({ud["phone"]})')

    # ── Cell Towers ───────────────────────────────────────
    def _create_cell_towers(self):
        from apps.tracking.models import CellTower

        towers = [
            {'tower_code': 'TOWER-MP-A1042', 'operator': 'BSNL',    'lat': 23.2720, 'lng': 77.4020,
             'mcc': 404, 'mnc': 1, 'lac': 1001, 'cell_id': 42001,
             'coverage_radius_m': 4000, 'technology': '2G'},
            {'tower_code': 'TOWER-MP-B2087', 'operator': 'Airtel',   'lat': 23.2480, 'lng': 77.4350,
             'mcc': 404, 'mnc': 10, 'lac': 1002, 'cell_id': 87002,
             'coverage_radius_m': 3500, 'technology': '3G'},
            {'tower_code': 'TOWER-MP-C3014', 'operator': 'Jio',      'lat': 23.2550, 'lng': 77.3950,
             'mcc': 404, 'mnc': 88, 'lac': 1003, 'cell_id': 14003,
             'coverage_radius_m': 5000, 'technology': '4G'},
            {'tower_code': 'TOWER-MP-D4022', 'operator': 'BSNL',    'lat': 23.2900, 'lng': 77.4600,
             'mcc': 404, 'mnc': 1, 'lac': 1004, 'cell_id': 22004,
             'coverage_radius_m': 6000, 'technology': '2G'},
            {'tower_code': 'TOWER-MP-E5031', 'operator': 'Vi',       'lat': 23.2200, 'lng': 77.4100,
             'mcc': 404, 'mnc': 20, 'lac': 1005, 'cell_id': 31005,
             'coverage_radius_m': 3000, 'technology': '3G'},
        ]

        for td in towers:
            tower, created = CellTower.objects.get_or_create(
                tower_code=td['tower_code'], defaults=td
            )
            status = '✅ created' if created else '⏭  exists'
            self.stdout.write(f'  {status}: tower {td["tower_code"]} ({td["operator"]})')

    # ── Routes ────────────────────────────────────────────
    def _create_routes(self):
        from apps.routes.models import Route, Stop
        from apps.users.models import User

        owner = User.objects.filter(role='owner').first()

        routes_data = [
            {
                'name': 'Kheda Express',
                'from_location': 'Kheda', 'to_location': 'Bhopal Central',
                'distance_km': 72, 'fare_min': 35, 'fare_max': 50,
                'stops': [
                    (1, 'Kheda Bus Stand',    23.3100, 77.3500),
                    (2, 'Nimli Chauraha',     23.2900, 77.3750),
                    (3, 'Raisen Road',        23.2700, 77.4000),
                    (4, 'Bhopal Central',     23.2599, 77.4126),
                ]
            },
            {
                'name': 'Morpura Local',
                'from_location': 'Morpura', 'to_location': 'Indore',
                'distance_km': 145, 'fare_min': 65, 'fare_max': 90,
                'stops': [
                    (1, 'Morpura Village',    23.3500, 77.5000),
                    (2, 'Devpur Bypass',      23.2800, 77.4800),
                    (3, 'Indore Bus Terminal',22.7196, 75.8577),
                ]
            },
        ]

        for rd in routes_data:
            stops_data = rd.pop('stops')
            route, created = Route.objects.get_or_create(
                name=rd['name'],
                defaults={**rd, 'is_active': True, 'created_by': owner}
            )
            for order, name, lat, lng in stops_data:
                Stop.objects.get_or_create(
                    route=route, order=order,
                    defaults={'name': name, 'lat': lat, 'lng': lng,
                              'distance_from_start_km': order * 18}
                )
            status = '✅ created' if created else '⏭  exists'
            self.stdout.write(f'  {status}: route — {route.name}')

    # ── Vehicles ──────────────────────────────────────────
    def _create_vehicles(self):
        from apps.vehicles.models import Vehicle
        from apps.users.models import User
        from apps.routes.models import Route

        owner  = User.objects.filter(role='owner').first()
        driver = User.objects.filter(role='driver').first()
        route1 = Route.objects.filter(name='Kheda Express').first()
        route2 = Route.objects.filter(name='Morpura Local').first()

        vehicles_data = [
            {'reg_number': 'MP04AB1234', 'bus_code': 'A01', 'model_name': 'Tata Starbus',
             'capacity': 40, 'status': 'active', 'rto_verified': True, 'route': route1},
            {'reg_number': 'MP09GH5678', 'bus_code': 'B07', 'model_name': 'Ashok Leyland',
             'capacity': 32, 'status': 'active', 'rto_verified': True, 'route': route2},
            {'reg_number': 'MP04CD9012', 'bus_code': 'C12', 'model_name': 'Volvo 9400',
             'capacity': 45, 'status': 'active', 'rto_verified': True, 'route': route1},
            {'reg_number': 'MP15EF3456', 'bus_code': 'D03', 'model_name': 'Tata LP 909',
             'capacity': 28, 'status': 'pending', 'rto_verified': False, 'route': route2},
        ]

        for vd in vehicles_data:
            vehicle, created = Vehicle.objects.get_or_create(
                reg_number=vd['reg_number'],
                defaults={**vd, 'owner': owner, 'driver': driver,
                          'manufacture_year': 2020}
            )
            status = '✅ created' if created else '⏭  exists'
            self.stdout.write(f'  {status}: vehicle {vd["bus_code"]} ({vd["reg_number"]})')

    # ── Schedules ─────────────────────────────────────────
    def _create_schedules(self):
        from apps.routes.models import Schedule, Route
        from apps.vehicles.models import Vehicle
        import datetime

        route1 = Route.objects.filter(name='Kheda Express').first()
        route2 = Route.objects.filter(name='Morpura Local').first()
        v_a01  = Vehicle.objects.filter(bus_code='A01').first()
        v_b07  = Vehicle.objects.filter(bus_code='B07').first()

        if not (route1 and route2 and v_a01 and v_b07):
            self.stdout.write(self.style.WARNING('  ⚠ Skipping schedules — vehicles/routes not found'))
            return

        schedules = [
            {'vehicle': v_a01, 'route': route1,
             'departure': datetime.time(6, 30), 'arrival': datetime.time(9, 0),
             'days': 'daily'},
            {'vehicle': v_a01, 'route': route1,
             'departure': datetime.time(15, 30), 'arrival': datetime.time(18, 0),
             'days': 'daily'},
            {'vehicle': v_b07, 'route': route2,
             'departure': datetime.time(7, 0), 'arrival': datetime.time(9, 30),
             'days': 'daily'},
            {'vehicle': v_b07, 'route': route2,
             'departure': datetime.time(14, 0), 'arrival': datetime.time(16, 30),
             'days': 'daily'},
        ]

        for sd in schedules:
            sched, created = Schedule.objects.get_or_create(
                vehicle=sd['vehicle'], route=sd['route'],
                departure=sd['departure'],
                defaults={**sd, 'is_active': True}
            )
            status = '✅ created' if created else '⏭  exists'
            self.stdout.write(f'  {status}: schedule {sched.vehicle.bus_code} @ {sched.departure}')
