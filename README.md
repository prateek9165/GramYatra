# GramYatra
This demo project that is mainly focused on providing proper connectivity by the means of transport to the rural areas to urban areas, small cities and to multiple villages. It will mainly behave like a link or a network that will provide service or the connections to users of cities and rural areas to others areas that will help visitors to know more deeply about the vehicles and shouldn't have to wait for multiple hours at the stop.

## Project Structure

```
gramyatra/
├── gramyatra/              # Core Django config
│   ├── settings.py         # All settings (DB, JWT, Redis, SMS, CORS)
│   ├── urls.py             # Root URL routing
│   ├── asgi.py             # HTTP + WebSocket (Django Channels)
│   ├── wsgi.py             # WSGI for HTTP-only deployments
│   └── celery.py           # Async task queue
│
├── apps/
│   ├── users/              # Auth, RBAC, user profiles
│   │   ├── models.py       # User, DriverProfile, OwnerProfile
│   │   ├── serializers.py  # Register (4 roles), Login, Profile
│   │   ├── permissions.py  # IsConsumerOrAbove, IsRTOOnly, etc.
│   │   ├── views/
│   │   │   ├── auth_views.py   # Register, Login, Logout, Me
│   │   │   └── user_views.py   # UserList, UserDetail, DutyToggle
│   │   └── urls/
│   │       ├── auth_urls.py
│   │       └── user_urls.py
│   │
│   ├── vehicles/           # Fleet management
│   │   ├── models.py       # Vehicle, VehicleDocument
│   │   ├── serializers.py  # Vehicle CRUD + Nearby + Search
│   │   ├── views.py        # NearbyVehicles, Search, CRUD, DocUpload
│   │   └── urls.py
│   │
│   ├── tracking/           # Cell-tower location engine
│   │   ├── models.py       # CellTower, VehicleTracking
│   │   ├── services.py     # Triangulation algorithm (RSSI → lat/lng)
│   │   ├── consumers.py    # WebSocket consumers (live tracking)
│   │   ├── routing.py      # WebSocket URL patterns
│   │   ├── views.py        # LocationUpdate, LiveLocation, History
│   │   ├── tasks.py        # Cleanup old tracking points
│   │   └── urls.py
│   │
│   ├── routes/             # Route & schedule management
│   │   ├── models.py       # Route, Stop, Schedule
│   │   ├── serializers.py
│   │   ├── views.py        # Search, TodaySchedule, AI query
│   │   └── urls.py
│   │
│   ├── notifications/      # SMS, push, arrival alerts, emergency
│   │   ├── models.py       # Notification, SMSLog, AlertSubscription, Emergency
│   │   ├── tasks.py        # send_sms_task, check_bus_arrival_alerts
│   │   ├── views.py        # NotifList, SetAlert, Emergency, SMSLog
│   │   └── urls.py
│   │
│   └── rto/                # RTO verification & compliance
│       ├── models.py       # VerificationRecord, ComplianceFlag, AuditLog
│       ├── serializers.py
│       ├── views.py        # Dashboard, Verify, Flags, LiveMap, Export
│       ├── tasks.py        # check_expiring_documents
│       └── urls.py
├── templates
│
├── manage.py
└── requirements.txt


