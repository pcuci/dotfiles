
# ~/.*

Portable dotfiles for a consistent and familiar workflow

```bash
git clone https://github.com/pcuci/dotfiles.git ~/.dotfiles && cd ~/.dotfiles

# Remove default configurations to link with dotfiles
diff ~/.profile ./.profile
rm ~/.profile
diff ~/.bash_logout ./.bash_logout
rm ~/.bash_logout

./install
```

Set up SSH keys.

```bash
cd ~/.dotfiles
./generate-ssh-keys
```

Register new keys with GitHub and GitLab:

- [GitHub SSH Keys](https://github.com/settings/keys)
- [GitLab SSH Keys](https://gitlab.com/-/profile/keys)

Synchronize SSH configurations between host and guest systems.

```bash
cd ~/.dotfiles
./ssh_sync --from=host --to=wsl --host-username=pcuciureanu # or pcuci
# ./ssh_sync --from=wsl --to=host --host-username=pcuciureanu
```

Update git remotes.

```bash
cd ~/.dotfiles
git remote set-url origin git@github.com:pcuci/dotfiles.git
git remote -v # to confirm changes
```

## License

Ethically sourced under the [Atmosphere License](https://www.open-austin.org/atmosphere-license/)—like open source, for good.
