FROM archlinux:base-devel

ARG USERNAME=radek
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN pacman -Syu --noconfirm sudo git mise \
    && groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME

RUN git clone https://aur.archlinux.org/yay-bin.git /tmp/yay-bin

WORKDIR /tmp/yay-bin

RUN makepkg -si --noconfirm && rm -rf /tmp/yay-bin

WORKDIR /home/$USERNAME
