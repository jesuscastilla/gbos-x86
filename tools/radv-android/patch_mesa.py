#!/usr/bin/env python3
"""Run from the Mesa source root; idempotent.

RADV's own vkGetAndroidHardwareBufferPropertiesANDROID returns format UNDEFINED / externalFormat 0 for a YV12 buffer, so Skia fails
("Failed to create valid YCbCr conversion information") and SurfaceFlinger aborts. Renaming it makes the entrypoint table fall back to
the common vk_common_ implementation, which reports YV12 as external format G8_B8_R8_3PLANE_420.

GBOS Android's minigbm backend cannot allocate TMZ-protected buffers. Disable RADV's TMZ capability so Android does not select protected
rendering paths that the allocator cannot satisfy."""
import sys

P = 'src/amd/vulkan/radv_android.c'
OLD = 'VkResult\nradv_GetAndroidHardwareBufferPropertiesANDROID('
NEW = 'static VkResult __attribute__((unused))\ngbos_unused_radv_GetAndroidHardwareBufferPropertiesANDROID('
TMZ_P = 'src/amd/vulkan/radv_physical_device.c'
TMZ_OLD = '''bool
radv_tmz_enabled(const struct radv_physical_device *pdev)
{
   const struct radv_instance *instance = radv_physical_device_instance(pdev);

   /* TODO: Fix GFX/SDMA rings hang on GFX9 APUs. */
   const bool radv_supports_tmz = pdev->info.gfx_level >= GFX10 || pdev->info.family == CHIP_VEGA10;

   return pdev->info.has_tmz_support && radv_supports_tmz && !(RADV_DEBUG(instance, NO_TMZ));
}'''
TMZ_NEW = '''bool
radv_tmz_enabled(const struct radv_physical_device *pdev)
{
    (void)pdev;
   return false;
}'''
TMZ_PREVIOUS = '''bool
radv_tmz_enabled(const struct radv_physical_device *pdev)
{
   return false;
}'''

def patch_once(path, old, new, previous=None):
    source = open(path).read()
    if new in source:
        print('already patched:', path)
    elif previous and previous in source:
        open(path, 'w').write(source.replace(previous, new))
        print('updated patch:', path)
    elif source.count(old) != 1:
        sys.exit(f'{path}: anchor found {source.count(old)} times')
    else:
        open(path, 'w').write(source.replace(old, new))
        print('patched:', path)


patch_once(P, OLD, NEW)
patch_once(TMZ_P, TMZ_OLD, TMZ_NEW, TMZ_PREVIOUS)
