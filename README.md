<!--
Avoid using this README file for information that is maintained or published elsewhere, e.g.:

* metadata.yaml > published on Charmhub
* documentation > published on (or linked to from) Charmhub
* detailed contribution guide > documentation or CONTRIBUTING.md

Use links instead.
-->

# traefik-k8s-path-redirector

Charmhub package name: traefik-k8s-path-redirector
More information: https://charmhub.io/traefik-k8s-path-redirector

A workloadless charm that publishes a Traefik route for path redirects.

Redirect to your content from the base domain. E.g. if `traefik-k8s` is serving your content at `https://jenkins.example.com/k8s-model-example-com-jenkins-k8s-0/`, use this charm with `direct_path_redirects='{"/": "/k8s-model-example-com-jenkins-k8s-0"}` to redirect to your app from `https://jenkins.example.com/`

## Other resources

<!-- If your charm is documented somewhere else other than Charmhub, provide a link separately. -->

- [Read more](https://example.com)

- [Contributing](CONTRIBUTING.md) <!-- or link to other contribution documentation -->

- See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
