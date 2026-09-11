## Hard Constraints
- Virtual machine network uses NAT configuration to enable internet access
- Windows FlClash TUN mode with virtual network adapter is used to route virtual machine traffic for境外 resource access
- Virtual machine must not have local proxy software (mihomo) or proxy environment variables (http_proxy/https_proxy/all_proxy) configured
- Virtual machine memory should be set to 40-44 GB (64GB host total) to prevent host memory exhaustion
- Virtual machine CPU configuration: 6 vCPU (1 processor × 6 cores) to avoid scheduling deadlocks
- Virtualization engine must enable Intel VT-x/EPT for Docker functionality
- systemd-oomd must be disabled and masked to prevent compilation process being killed due to memory pressure
- Ubuntu 22.04 sudo requires password input; assistant cannot execute password-protected sudo commands in non-interactive SSH sessions
- tracker-miner-fs-3 service must be masked and disabled to prevent CPU resource theft during compilation

## Engineering Conventions
- SSH public keys are stored in ~/.ssh/authorized_keys with 600 permissions
- Environment variables for API keys are added to ~/.bash_profile (instead of .bashrc) to ensure loading in all terminal sessions
- SSH configuration uses Host aliases (e.g., my-vm) with IdentityFile specified for key-based authentication
- Build scripts (e.g., SNM970_A15_build.sh) use hardcoded paths without '-irix' suffix; create symbolic links with matching names to point to actual '-irix' suffixed repository directories
- Compilation commands should be pasted one by one to avoid line concatenation issues
- SNM970_A15_build.sh uses JOBS=8 for parallel compilation (modified from $(nproc))

## Lessons Learned
- Allocating vCPU equal to host logical processors causes scheduling deadlocks; limit to 50% of host cores
- Overcommitting VM memory beyond host available capacity leads to system-wide performance degradation
- Corrupted toolchain binaries (e.g., toybox) in kernel_platform/build-tools cause silent script failures during prepare_vendor.sh execution
- Ubuntu 22.04/24.04 systemd-oomd will kill compilation processes under memory pressure; must disable and mask the service
- Compilation scripts (e.g., SNM970_A15_build.sh) delete specific Android.mk/Android.bp files in kernel_platform directory during execution; these deletions are normal and not accidental