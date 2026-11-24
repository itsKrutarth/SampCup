/** The official SAMP Cup logo (the same image as the header and the home page). `size` is its
 * height in pixels; the width follows the logo's shape. */
export default function Logo({ size = 40 }: { size?: number }) {
  return (
    <img
      className="logo"
      src="/brand/samp-cup-logo.webp"
      width={Math.round((size * 532) / 642)}
      height={size}
      alt=""
    />
  )
}
