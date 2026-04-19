# Maintainer: Your Name <your.email@example.com>
# Contributor: 

pkgname=fighter-1
gitname=Fighter-1
pkgver=1.0.0
pkgrel=1
pkgdesc="A fighting game written in Python."
arch=('any')
url="https://github.com/yourusername/Fighter-1"
license=('MIT')
depends=('python' 'python-pygame')
makedepends=()
source=("$pkgname-$pkgver.tar.gz"
        "icon.png")
sha256sums=('SKIP'
            'SKIP')

build() {
  cd "$srcdir/$pkgname-$pkgver"
  # No build step required for Python scripts
}

package() {
  cd "$srcdir/$pkgname-$pkgver"
  install -Dm755 main.py "$pkgdir/usr/bin/fighter-1"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
  install -Dm644 assets/original/gfx/icon.png "$pkgdir/usr/share/pixmaps/fighter-1.png"
  install -Dm644 Fighter.desktop "$pkgdir/usr/share/applications/fighter-1.desktop"
  # Copy assets
  cp -r assets "$pkgdir/usr/share/fighter-1/assets"
  cp -r fighter "$pkgdir/usr/share/fighter-1/fighter"
}
