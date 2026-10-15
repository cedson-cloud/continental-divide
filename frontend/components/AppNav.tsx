"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { SidebarContours } from "./Contours";
import { Icon, IconName, Logo } from "./icons";

type NavItem = { href: string; label: string; icon: IconName; matches: (path: string) => boolean };

const NAV_ITEMS: NavItem[] = [
  { href: "/guide", label: "How to use this", icon: "help", matches: (p) => p.startsWith("/guide") },
  {
    href: "/",
    label: "New request",
    icon: "plus",
    matches: (p) => p === "/" || p.startsWith("/request/"),
  },
  {
    href: "/queue",
    label: "Queue",
    icon: "inbox",
    matches: (p) => p.startsWith("/queue") || p.startsWith("/requests/"),
  },
  {
    href: "/catalog",
    label: "Tracking plan",
    icon: "book",
    matches: (p) => p.startsWith("/catalog"),
  },
  { href: "/admin", label: "Governance", icon: "shield", matches: (p) => p.startsWith("/admin") },
];

export function AppNav() {
  const pathname = usePathname() ?? "/";
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return (
    <header className="sidebar">
      <div className="sidebar-top">
        <Link href="/" className="sidebar-brand" onClick={closeMenu}>
          <Logo />
          <span>
            <span className="sidebar-brand-name">Continental Divide</span>
            <span className="sidebar-brand-tag">Tracking governance</span>
          </span>
        </Link>
        <button
          type="button"
          className="btn sidebar-menu-button"
          aria-expanded={menuOpen}
          aria-controls="main-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <Icon name={menuOpen ? "close" : "menu"} />
          Menu
        </button>
      </div>
      <nav id="main-nav" aria-label="Main" className={`sidebar-nav${menuOpen ? " open" : ""}`}>
        {NAV_ITEMS.map((item) => {
          const current = item.matches(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={current ? "current" : undefined}
              aria-current={current ? "page" : undefined}
              onClick={closeMenu}
            >
              <Icon name={item.icon} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <SidebarContours />
    </header>
  );
}
