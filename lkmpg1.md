1. Introduction

The Linux Kernel Module Programming Guide is a free book; you may reproduce and/or modify it under the terms of the [Open Software License](https://opensource.org/licenses/OSL-3.0), version 3.0.

This book is distributed in the hope that it would be useful, but without any warranty, without even the implied warranty of merchantability or fitness for a particular purpose.

The author encourages wide distribution of this book for personal or commercial use, provided the above copyright notice remains intact and the method adheres to the provisions of the [Open Software License](https://opensource.org/licenses/OSL-3.0). In summary, you may copy and distribute this book free of charge or for a profit. No explicit permission is required from the author for reproduction of this book in any medium, physical or electronic.

Derivative works and translations of this document must be placed under the Open Software License, and the original copyright notice must remain intact. If you have contributed new material to this book, you must make the material and source code available for your revisions. Please make revisions and updates available directly to the document maintainer, Jim Huang <jserv@ccns.ncku.edu.tw>. This will allow for the merging of updates and provide consistent revisions to the Linux community.

If you publish or distribute this book commercially, donations, royalties, and/or printed copies are greatly appreciated by the author and the [Linux Documentation Project](https://tldp.org/) (LDP). Contributing in this way shows your support for free software and the LDP. If you have questions or comments, please contact the address above.

<a name="sec:authorship"></a>

## 1.1. Authorship

The Linux Kernel Module Programming Guide was originally written for the 2.2 kernels by Ori Pomerantz. Eventually, Ori no longer had time to maintain the document. After all, the Linux kernel is a fast moving target. Peter Jay Salzman took over maintenance and updated it for the 2.4 kernels. Eventually, Peter no longer had time to follow developments with the 2.6 kernel, so Michael Burian became a co-maintainer to update the document for the 2.6 kernels. Bob Mottram updated the examples for 3.8+ kernels. Jim Huang upgraded to recent kernel versions (v5.x) and revised the LaTeX document.

<a name="sec:acknowledgements"></a>

## 1.2. Acknowledgements

The following people have contributed corrections or good suggestions:

2011eric, 25077667, Arush Sharma, asas1asas200, Benno Bielmeier, Bob Lee, Brad Baker, ccs100203, Chih-Yu Chen, Ching-Hua (Vivian) Lin, ChinYikMing, Cyril Brulebois, Daniele Paolo Scarpazza, David Porter, demonsome, Dimo Velev, Ekang Monyet, fennecJ, Francois Audeon, gagachang, Gilad Reti, Horst Schirmeier, Hsin-Hsiang Peng, Ignacio Martin, JianXing Wu, linD026, lyctw, manbing, Marconi Jiang, mengxinayan, RinHizakura, Roman Lakeev, Stacy Prowell, Steven Lung, Tristan Lelong, Tucker Polomik, VxTeemo, Wei-Lun Tsai, xatier, Ylowy.

<a name="sec:kernelmod"></a>

## 1.3. What Is A Kernel Module?

So, you want to write a kernel module. You know C, you have written a few normal programs to run as processes, and now you want to get to where the real action is, to where a single wild pointer can wipe out your file system and a core dump means a reboot.

What exactly is a kernel module? Modules are pieces of code that can be loaded and unloaded into the kernel upon demand. They extend the functionality of the kernel without the need to reboot the system. For example, one type of module is the device driver, which allows the kernel to access hardware connected to the system. Without modules, we would have to build monolithic kernels and add new functionality directly into the kernel image. Besides having larger kernels, this has the disadvantage of requiring us to rebuild and reboot the kernel every time we want new functionality.

<a name="sec:packages"></a>

## 1.4. Kernel module package

Linux distributions provide the commands `modprobe`, `insmod` and `depmod` within a package.

On Ubuntu/Debian:

    sudo apt-get install build-essential kmod

On Arch Linux:

    sudo pacman -S gcc kmod

<a name="sec:modutils"></a>

## 1.5. What Modules are in my Kernel?

To discover what modules are already loaded within your current kernel use the command `lsmod`.

    sudo lsmod

Modules are stored within the file `/proc/modules`, so you can also see them with:

    sudo cat /proc/modules

This can be a long list, and you might prefer to search for something particular. To search for the `fat` module:

    sudo lsmod | grep fat

<a name="sec:buildkernel"></a>

## 1.6. Do I need to download and compile the kernel?

For the purposes of following this guide you don't necessarily need to do that. However, it would be wise to run the examples within a test distribution running on a virtual machine in order to avoid any possibility of messing up your system.

<a name="sec:preparation"></a>

## 1.7. Before We Begin

Before we delve into code, there are a few issues we need to cover. Everyone's system is different and everyone has their own groove. Getting your first "hello world" program to compile and load correctly can sometimes be a trick. Rest assured, after you get over the initial hurdle of doing it for the first time, it will be smooth sailing thereafter.

1.  Modversioning. A module compiled for one kernel will not load if you boot a different kernel unless you enable `CONFIG_MODVERSIONS` in the kernel. We will not go into module versioning until later in this guide. Until we cover modversions, the examples in the guide may not work if you are running a kernel with modversioning turned on. However, most stock Linux distribution kernels come with it turned on. If you are having trouble loading the modules because of versioning errors, compile a kernel with modversioning turned off.

2.  Using X Window System. <a name="sec:using_x"></a> It is highly recommended that you extract, compile and load all the examples this guide discusses from a console. You should not be working on this stuff in X Window System.

    Modules can not print to the screen like `printf()` can, but they can log information and warnings, which ends up being printed on your screen, but only on a console. If you `insmod` a module from an xterm, the information and warnings will be logged, but only to your systemd journal. You will not see it unless you look through your `journalctl` . See [4](https://wikidocs.net/196795) for details. To have immediate access to this information, do all your work from the console.

3.  SecureBoot. Many contemporary computers are pre-configured with UEFI SecureBoot enabled. It is a security standard that can make sure the device boots using only software that is trusted by original equipment manufacturer. The default Linux kernel from some distributions have also enabled the SecureBoot. For such distributions, the kernel module has to be signed with the security key or you would get the "*ERROR: could not insert module*" when you insert your first hello world module:

        insmod ./hello-1.ko

    And then you can check further with `dmesg` and see the following text:

    *Lockdown: insmod: unsigned module loading is restricted; see man kernel lockdown.7*

    If you got this message, the simplest way is to disable the UEFI SecureBoot from the PC/laptop boot menu to have your "hello-1" to be inserted. Of course you can go through complicated steps to generate keys, install keys to your system, and finally sign your module to make it work. However, this is not suitable for beginners. You could read and follow the steps in [SecureBoot](https://wiki.debian.org/SecureBoot) if you are interested.
