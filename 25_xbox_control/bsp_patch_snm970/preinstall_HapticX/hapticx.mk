ifeq ($(strip $(TARGET_PRODUCT)), qssi)
PRODUCT_PACKAGES += \
    HapticX \
    privapp-permissions_hapticx.xml \
    default-permissions-com.meig.hapticx.xml
endif
