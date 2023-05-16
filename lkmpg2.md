2. Headers

Before you can build anything you'll need to install the header files for your kernel.

On Ubuntu/Debian:

    sudo apt-get update
    apt-cache search linux-headers-`uname -r`

This will tell you what kernel header files are available. Then for example:

    sudo apt-get install kmod linux-headers-5.4.0-80-generic

On Arch Linux:

    sudo pacman -S linux-headers
