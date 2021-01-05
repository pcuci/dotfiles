# ~/.*

Portable dotfiles for a consistent familiar workflow

``` bash
git clone https://github.com/pcuci/dotfiles.git ~/.dotfiles
```

Install. Might need to delete some pre-generated files like `~/.profile`

``` bash
cd ~/.dotfiles
./install
```

Setup ssh keys.

``` bash
cd ~/.dotfiles
./generate-ssh-keys
```

Sync with host/guest.

``` bash
cd ~/.dotfiles
./ssh_sync_host_to_wsl # or
./ssh_sync_wsl_to_host
```

Add new keys to GitHub and GitLab:

- [GitHub SSH Keys](https://github.com/settings/keys)
- [GitLab SSH Keys](https://gitlab.com/-/profile/keys)

Update git remotes to use ssh.

``` bash
cd ~/.dotfiles
git remote set-url origin git@github.com:pcuci/dotfiles.git
git remote -v # to verify
```

## License

Ethically sourced under the [Atmosphere License](https://www.open-austin.org/atmosphere-license/)—like open source, for good.
