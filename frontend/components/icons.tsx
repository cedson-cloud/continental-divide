const PATHS = {
  plus: <path d="M10 4v12M4 10h12" />,
  inbox: (
    <>
      <path d="M3 11l2-6h10l2 6v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
      <path d="M3 11h4l1 2h4l1-2h4" />
    </>
  ),
  book: (
    <>
      <path d="M5 3h9a1 1 0 0 1 1 1v13H6.5A1.5 1.5 0 0 1 5 15.5z" />
      <path d="M5 15.5A1.5 1.5 0 0 1 6.5 14H15" />
    </>
  ),
  shield: <path d="M10 3l6 2.5V10c0 3.5-2.6 6-6 7-3.4-1-6-3.5-6-7V5.5z" />,
  menu: <path d="M3.5 6h13M3.5 10h13M3.5 14h13" />,
  close: <path d="M5.5 5.5l9 9M14.5 5.5l-9 9" />,
  check: <path d="M4.5 10.5l3.5 3.5 7.5-8" />,
  pencil: <path d="M13 4.5l2.5 2.5L7.5 15H5v-2.5z" />,
  play: <path d="M7 5l8 5-8 5z" />,
  chevron: <path d="M8 5.5l4.5 4.5L8 14.5" />,
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      viewBox="0 0 20 20"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}

// A ridge with a marker on the high point: the divide the product is named for.
export function Logo() {
  return (
    <svg viewBox="0 0 32 32" width={30} height={30} fill="none" aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="30" height="30" rx="9" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M6 22.5L12.5 12l3.5 5 4.5-8.5 5.5 14"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="20.5" cy="8.5" r="1.8" fill="currentColor" />
    </svg>
  );
}
