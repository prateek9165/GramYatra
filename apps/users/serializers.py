"""
GramYatra — Users Serializers
Registration, Login, Profile serializers for all 4 roles
"""

from django.contrib.auth.hashers import make_password, check_password
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, DriverProfile, OwnerProfile


# ─────────────────────────────────────────
# REGISTRATION SERIALIZERS
# ─────────────────────────────────────────

class ConsumerRegisterSerializer(serializers.ModelSerializer):
    captcha = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['name', 'phone', 'preferred_language', 'captcha']

    def validate_phone(self, value):
        value = value.strip().replace(' ', '').replace('-', '')
        if len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError('Enter a valid 10-digit mobile number.')
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('This phone number is already registered.')
        return value

    def validate_captcha(self, value):
        # CAPTCHA is validated client-side; server stores a session token.
        # In production, integrate a CAPTCHA service (e.g. hCaptcha).
        if not value or len(value) < 4:
            raise serializers.ValidationError('Invalid CAPTCHA.')
        return value

    def create(self, validated_data):
        validated_data.pop('captcha')
        user = User.objects.create_user(
            phone=validated_data['phone'],
            name=validated_data['name'],
            role=User.Role.CONSUMER,
            **{k: v for k, v in validated_data.items() if k not in ['phone', 'name']}
        )
        return user


class DriverRegisterSerializer(serializers.ModelSerializer):
    license_number   = serializers.CharField(write_only=True)
    license_document = serializers.FileField(write_only=True, required=False)
    license_expiry   = serializers.DateField(write_only=True, required=False)
    captcha          = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['name', 'phone', 'preferred_language', 'license_number', 'license_document', 'license_expiry', 'captcha']

    def validate_phone(self, value):
        value = value.strip().replace(' ', '')
        if len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError('Enter a valid 10-digit mobile number.')
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('Phone number already registered.')
        return value

    def validate_license_number(self, value):
        if DriverProfile.objects.filter(license_number=value).exists():
            raise serializers.ValidationError('This license number is already registered.')
        return value

    def create(self, validated_data):
        validated_data.pop('captcha')
        license_number   = validated_data.pop('license_number')
        license_document = validated_data.pop('license_document', None)
        license_expiry   = validated_data.pop('license_expiry', None)

        user = User.objects.create_user(
            phone=validated_data.pop('phone'),
            name=validated_data.pop('name'),
            role=User.Role.DRIVER,
            **validated_data
        )
        DriverProfile.objects.create(
            user=user,
            license_number=license_number,
            license_document=license_document,
            license_expiry=license_expiry,
        )
        return user


class OwnerRegisterSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(required=False, write_only=True)
    captcha      = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['name', 'phone', 'preferred_language', 'company_name', 'captcha']

    def validate_phone(self, value):
        value = value.strip().replace(' ', '')
        if len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError('Enter a valid 10-digit mobile number.')
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('Phone number already registered.')
        return value

    def create(self, validated_data):
        validated_data.pop('captcha')
        company_name = validated_data.pop('company_name', '')
        user = User.objects.create_user(
            phone=validated_data.pop('phone'),
            name=validated_data.pop('name'),
            role=User.Role.OWNER,
            **validated_data
        )
        OwnerProfile.objects.create(user=user, company_name=company_name)
        return user


class RTORegisterSerializer(serializers.ModelSerializer):
    passkey = serializers.CharField(write_only=True)
    captcha = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['name', 'phone', 'passkey', 'captcha']

    def validate_passkey(self, value):
        if value != settings.RTO_PASSKEY:
            raise serializers.ValidationError('Invalid RTO passkey.')
        return value

    def validate_phone(self, value):
        value = value.strip().replace(' ', '')
        if len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError('Enter a valid 10-digit mobile number.')
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('Phone number already registered.')
        return value

    def create(self, validated_data):
        validated_data.pop('captcha')
        passkey = validated_data.pop('passkey')
        user = User.objects.create_user(
            phone=validated_data.pop('phone'),
            name=validated_data.pop('name'),
            role=User.Role.RTO,
        )
        user.rto_passkey_hash = make_password(passkey)
        user.save()
        return user


# ─────────────────────────────────────────
# LOGIN SERIALIZER
# ─────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    phone   = serializers.CharField()
    captcha = serializers.CharField()
    passkey = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        phone = data.get('phone', '').strip().replace(' ', '')
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({'phone': 'No account found with this number.'})

        if not user.is_active:
            raise serializers.ValidationError({'phone': 'Your account has been deactivated.'})

        # RTO passkey check
        if user.is_rto:
            passkey = data.get('passkey', '')
            if not passkey:
                raise serializers.ValidationError({'passkey': 'Passkey is required for RTO login.'})
            if not check_password(passkey, user.rto_passkey_hash):
                # Also allow env passkey for convenience
                if passkey != settings.RTO_PASSKEY:
                    raise serializers.ValidationError({'passkey': 'Invalid RTO passkey.'})

        data['user'] = user
        return data

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['name'] = user.name
        return {
            'refresh': str(refresh),
            'access':  str(refresh.access_token),
        }


# ─────────────────────────────────────────
# PROFILE SERIALIZERS
# ─────────────────────────────────────────

class DriverProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DriverProfile
        fields = ['license_number', 'license_document', 'license_expiry',
                  'is_rto_verified', 'total_trips', 'rating', 'is_on_duty']


class OwnerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OwnerProfile
        fields = ['operator_id', 'company_name', 'is_rto_verified', 'rto_verified_at']


class UserProfileSerializer(serializers.ModelSerializer):
    driver_profile = DriverProfileSerializer(read_only=True)
    owner_profile  = OwnerProfileSerializer(read_only=True)

    class Meta:
        model  = User
        fields = ['id', 'name', 'phone', 'role', 'is_verified', 'preferred_language',
                  'sms_alerts_enabled', 'push_alerts_enabled', 'offline_cache_enabled',
                  'date_joined', 'driver_profile', 'owner_profile']
        read_only_fields = ['id', 'phone', 'role', 'date_joined']


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for lists."""
    class Meta:
        model  = User
        fields = ['id', 'name', 'phone', 'role', 'is_active', 'is_verified', 'date_joined']
