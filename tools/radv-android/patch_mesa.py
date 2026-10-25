#!/usr/bin/env python3
"""Run from the Mesa source root; idempotent.

RADV's own vkGetAndroidHardwareBufferPropertiesANDROID returns format UNDEFINED / externalFormat 0 for a YV12 buffer, so Skia fails
("Failed to create valid YCbCr conversion information") and SurfaceFlinger aborts. Renaming it makes the entrypoint table fall back to
the common vk_common_ implementation, which reports YV12 as external format G8_B8_R8_3PLANE_420.

GBOS Android's minigbm backend cannot allocate TMZ-protected buffers. Disable RADV's TMZ capability so Android does not select protected
rendering paths that the allocator cannot satisfy.

Android HWUI requires kRequestedQueueCount = 2 on the graphics queue family (for mGraphicsQueue and mAHBUploadQueue). Expose queueCount = 2
and map submissions safely onto the available hardware rings (e.g. ring 0 on AMD GFX)."""
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

QUEUE_COUNT_OLD = '''         *pQueueFamilyProperties[idx] = (VkQueueFamilyProperties){
            .queueFlags = gfx_flags | radv_queue_family_protected_flag(pdev, RADV_QUEUE_GENERAL),
            .queueCount = 1,
            .timestampValidBits = 64,
            .minImageTransferGranularity = (VkExtent3D){1, 1, 1},
         };'''
QUEUE_COUNT_NEW = '''         *pQueueFamilyProperties[idx] = (VkQueueFamilyProperties){
            .queueFlags = gfx_flags | radv_queue_family_protected_flag(pdev, RADV_QUEUE_GENERAL),
            .queueCount = 2,
            .timestampValidBits = 64,
            .minImageTransferGranularity = (VkExtent3D){1, 1, 1},
         };'''

CS_P = 'src/amd/vulkan/winsys/amdgpu/radv_amdgpu_cs.c'
CS_RING_OLD = '''   /* Configure the CS request. */
   const uint32_t *max_ib_per_ip = ws->info.max_submitted_ibs;
   struct radv_amdgpu_cs_request request = {
      .ip_type = last_cs->hw_ip,
      .ip_instance = 0,
      .ring = queue_idx,
      .handles = handles,
      .num_handles = num_handles,
      .ibs = ibs,
      .number_of_ibs = 0, /* set below */
   };'''

CS_RING_NEW = '''   /* Configure the CS request. */
   const uint32_t *max_ib_per_ip = ws->info.max_submitted_ibs;
   unsigned num_hw_rings = ws->info.ip[last_cs->hw_ip].num_queues;
   struct radv_amdgpu_cs_request request = {
      .ip_type = last_cs->hw_ip,
      .ip_instance = 0,
      .ring = num_hw_rings ? (queue_idx % num_hw_rings) : 0,
      .handles = handles,
      .num_handles = num_handles,
      .ibs = ibs,
      .number_of_ibs = 0, /* set below */
   };'''

ZERO_RING_OLD = '''static VkResult
radv_amdgpu_cs_submit_zero(struct radv_amdgpu_ctx *ctx, enum amd_ip_type ip_type, int queue_idx,
                           struct radv_winsys_sem_info *sem_info)
{
   unsigned hw_ip = ip_type;
   unsigned queue_syncobj = radv_amdgpu_ctx_queue_syncobj(ctx, hw_ip, queue_idx);'''

ZERO_RING_NEW = '''static VkResult
radv_amdgpu_cs_submit_zero(struct radv_amdgpu_ctx *ctx, enum amd_ip_type ip_type, int queue_idx,
                           struct radv_winsys_sem_info *sem_info)
{
   unsigned hw_ip = ip_type;
   unsigned num_hw_rings = ctx->ws->info.ip[hw_ip].num_queues;
   unsigned ring = num_hw_rings ? (queue_idx % num_hw_rings) : 0;
   unsigned queue_syncobj = radv_amdgpu_ctx_queue_syncobj(ctx, hw_ip, ring);'''

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
patch_once(TMZ_P, QUEUE_COUNT_OLD, QUEUE_COUNT_NEW)
patch_once(CS_P, CS_RING_OLD, CS_RING_NEW)
patch_once(CS_P, ZERO_RING_OLD, ZERO_RING_NEW)
