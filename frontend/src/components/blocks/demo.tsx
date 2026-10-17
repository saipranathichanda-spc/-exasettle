import { HeroSection } from "@/components/blocks/hero-section-dark"

function HeroSectionDemo() {
  return (
    <HeroSection
      title="Welcome to Our Platform"
      subtitle={{
        regular: "Transform your ideas into ",
        gradient: "beautiful digital experiences",
      }}
      description="Transform your ideas into reality with our comprehensive suite of development tools and resources."
      ctaText="Get Started"
      ctaHref="/signup"
      bottomImage={{
        light: "https://cdn.21st.dev/assets/mirror/86/867a175524a0966eb144327b962159fa1ac4e1822b0cd857759b754306f3b0d4.png",
        dark: "https://cdn.21st.dev/assets/mirror/cf/cfc7a54d3246bd8216b45d7d01273476ee5ca661554db59d8ae3c46e74d85bc9.png",
      }}
      gridOptions={{
        angle: 65,
        opacity: 0.4,
        cellSize: 50,
        lightLineColor: "#4a4a4a",
        darkLineColor: "#2a2a2a",
      }}
    />
  )
}
export { HeroSectionDemo }
